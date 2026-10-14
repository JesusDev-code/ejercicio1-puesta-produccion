import random
from datetime import datetime, timedelta

from sqlalchemy import case, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import obtener_configuracion
from app.errores import Conflicto, Invalido, NoEncontrado
from app.esquemas import (
    EventoEntrada,
    EventoSalida,
    Recuento,
    ResumenEventos,
    Sensor,
    Tramo,
    TriajeEntrada,
)
from app.modelos import (
    Categoria,
    Estado,
    EstadoTriaje,
    EventoSeguridad,
    Incidente,
    Severidad,
    TipoEvento,
    Usuario,
    a_utc,
    ahora,
)
from app.repositorios import RepositorioEmpresas
from app.servicios.auditoria import auditar
from app.tiempo_real import difusor

NOMBRES_TIPO: dict[TipoEvento, str] = {
    TipoEvento.sondeo_rutas: "Sondeo de rutas",
    TipoEvento.fichero_sensible: "Acceso a fichero sensible",
    TipoEvento.fuerza_bruta: "Fuerza bruta de credenciales",
    TipoEvento.inyeccion: "Intento de inyección",
    TipoEvento.recorrido_rutas: "Recorrido de directorios",
    TipoEvento.escaner: "Escáner automatizado",
    TipoEvento.otro: "Actividad sospechosa",
}

CATEGORIA_DE_TIPO: dict[TipoEvento, Categoria] = {
    TipoEvento.sondeo_rutas: Categoria.acceso_no_autorizado,
    TipoEvento.fichero_sensible: Categoria.fuga_datos,
    TipoEvento.fuerza_bruta: Categoria.acceso_no_autorizado,
    TipoEvento.inyeccion: Categoria.acceso_no_autorizado,
    TipoEvento.recorrido_rutas: Categoria.acceso_no_autorizado,
    TipoEvento.escaner: Categoria.otro,
    TipoEvento.otro: Categoria.otro,
}

# Cada cuántas ingestas (de media) se purgan los eventos viejos. Barato y sin cron.
_PROBABILIDAD_PURGA = 1 / 200


async def ingestar(sesion: AsyncSession, eventos: list[EventoEntrada]) -> int:
    momento = ahora()
    codigos = {e.empresa for e in eventos if e.empresa}
    ids = await RepositorioEmpresas(sesion).ids_por_codigo(codigos)
    if desconocidos := codigos - ids.keys():
        # Mejor rechazar el lote que guardar eventos sin dueño: un sensor mal configurado
        # se ve en su log al momento, en vez de llenar el panel de eventos huérfanos
        raise Invalido(f"Empresa desconocida: {', '.join(sorted(desconocidos))}")
    filas = [
        EventoSeguridad(
            **e.model_dump(exclude={"empresa"}),
            empresa_id=ids[e.empresa] if e.empresa else None,
            fecha=momento,
        )
        for e in eventos
    ]
    sesion.add_all(filas)
    await sesion.flush()

    # Azar para repartir la purga en el tiempo, no para nada de seguridad
    if random.random() < _PROBABILIDAD_PURGA:  # noqa: S311  # nosec B311
        await purgar(sesion)
    await sesion.commit()

    for fila in filas:
        _difundir("nuevo", fila)
    return len(filas)


def _difundir(clase: str, evento: EventoSeguridad) -> None:
    """Difunde el evento a los paneles abiertos.
    `clase` distingue uno nuevo de un cambio de triaje."""
    carga = EventoSalida.model_validate(evento).model_dump_json()
    difusor.publicar(f'{{"clase":"{clase}","evento":{carga}}}')


async def purgar(sesion: AsyncSession) -> None:
    """Borra lo que supera la retención, salvo lo que ya es evidencia de una incidencia."""
    limite = ahora() - timedelta(days=obtener_configuracion().eventos_retencion_dias)
    await sesion.execute(
        delete(EventoSeguridad).where(
            EventoSeguridad.fecha < limite, EventoSeguridad.incidente_id.is_(None)
        )
    )


async def listar(
    sesion: AsyncSession,
    *,
    tipo: TipoEvento | None,
    severidad: Severidad | None,
    origen_ip: str | None,
    estado: EstadoTriaje | None = None,
    empresa_id: int | None = None,
    limite: int,
    desplazamiento: int,
) -> tuple[int, list[EventoSeguridad]]:
    consulta = select(EventoSeguridad)
    if empresa_id is not None:
        consulta = consulta.where(EventoSeguridad.empresa_id == empresa_id)
    if tipo:
        consulta = consulta.where(EventoSeguridad.tipo == tipo)
    if severidad:
        consulta = consulta.where(EventoSeguridad.severidad == severidad)
    if origen_ip:
        consulta = consulta.where(EventoSeguridad.origen_ip == origen_ip)
    if estado:
        consulta = consulta.where(EventoSeguridad.estado_triaje == estado)
    total = await sesion.scalar(select(func.count()).select_from(consulta.subquery()))
    pagina = consulta.order_by(EventoSeguridad.id.desc()).limit(limite).offset(desplazamiento)
    return total or 0, list(await sesion.scalars(pagina))


async def _contar(sesion: AsyncSession, *condiciones) -> int:
    return (await sesion.scalar(select(func.count(EventoSeguridad.id)).where(*condiciones))) or 0


async def _agrupar(
    sesion: AsyncSession, columna, desde: datetime, filtro: list, limite: int | None = None
):
    total = func.count(EventoSeguridad.id).label("total")
    consulta = (
        select(columna, total)
        .where(EventoSeguridad.fecha >= desde, *filtro)
        .group_by(columna)
        .order_by(total.desc())
    )
    if limite:
        consulta = consulta.limit(limite)
    return [Recuento(clave=str(clave), total=n) for clave, n in await sesion.execute(consulta)]


async def _tramos(
    sesion: AsyncSession, desde: datetime, segundos: int, cuantos: int, filtro: list
) -> list[Tramo]:
    """Recuento por tramos de tamaño fijo desde `desde`. En PostgreSQL agrupa la base de
    datos; en SQLite (tests) se agrupa aquí, porque no tiene una función de epoch fiable."""
    base = int(desde.timestamp()) // segundos * segundos
    cuentas: dict[int, int] = {}
    if sesion.bind.dialect.name == "postgresql":
        cubo = func.floor(func.extract("epoch", EventoSeguridad.fecha) / segundos)
        consulta = (
            select(cubo.label("cubo"), func.count(EventoSeguridad.id))
            .where(EventoSeguridad.fecha >= desde, *filtro)
            .group_by("cubo")
        )
        for cubo_n, n in await sesion.execute(consulta):
            cuentas[int(cubo_n) * segundos] = n
    else:
        fechas = await sesion.scalars(
            select(EventoSeguridad.fecha).where(EventoSeguridad.fecha >= desde, *filtro)
        )
        for fecha in fechas:
            inicio = int(a_utc(fecha).timestamp()) // segundos * segundos
            cuentas[inicio] = cuentas.get(inicio, 0) + 1

    return [
        Tramo(
            inicio=datetime.fromtimestamp(base + i * segundos, tz=desde.tzinfo),
            total=cuentas.get(base + i * segundos, 0),
        )
        for i in range(cuantos)
    ]


async def resumen(
    sesion: AsyncSession, horas: int, empresa_id: int | None = None
) -> ResumenEventos:
    momento = ahora()
    desde = momento - timedelta(hours=horas)
    hace_hora = momento - timedelta(hours=1)
    # Condición común a todas las métricas: el panel de un cliente no mezcla datos de otro
    filtro = [] if empresa_id is None else [EventoSeguridad.empresa_id == empresa_id]
    return ResumenEventos(
        horas=horas,
        total=await _contar(sesion, EventoSeguridad.fecha >= desde, *filtro),
        ultima_hora=await _contar(sesion, EventoSeguridad.fecha >= hace_hora, *filtro),
        ips_unicas=(
            await sesion.scalar(
                select(func.count(func.distinct(EventoSeguridad.origen_ip))).where(
                    EventoSeguridad.fecha >= desde, *filtro
                )
            )
        )
        or 0,
        criticos=await _contar(
            sesion,
            EventoSeguridad.fecha >= desde,
            EventoSeguridad.severidad == Severidad.critica,
            *filtro,
        ),
        por_tipo=await _agrupar(sesion, EventoSeguridad.tipo, desde, filtro),
        por_severidad=await _agrupar(sesion, EventoSeguridad.severidad, desde, filtro),
        top_ips=await _agrupar(sesion, EventoSeguridad.origen_ip, desde, filtro, limite=10),
        # El minuto/hora en curso es el último tramo: +1 para incluirlo
        por_minuto=await _tramos(sesion, momento - timedelta(minutes=59), 60, 60, filtro),
        por_hora=await _tramos(sesion, momento - timedelta(hours=167), 3600, 168, filtro),
    )


async def sensores(sesion: AsyncSession) -> list[Sensor]:
    """Estado de cada sensor según sus eventos: cuántos y cuándo llegó el último. Un sensor
    que deja de enviar se ve aquí antes que en ningún otro sitio."""
    desde = ahora() - timedelta(hours=24)
    consulta = (
        select(
            EventoSeguridad.servicio,
            EventoSeguridad.empresa_id,
            func.count(EventoSeguridad.id),
            func.sum(case((EventoSeguridad.fecha >= desde, 1), else_=0)),
            func.max(EventoSeguridad.fecha),
        )
        .group_by(EventoSeguridad.servicio, EventoSeguridad.empresa_id)
        .order_by(EventoSeguridad.servicio, EventoSeguridad.empresa_id)
    )
    return [
        Sensor(
            servicio=servicio,
            empresa_id=empresa_id,
            total=total,
            ultimas_24h=recientes or 0,
            ultimo=a_utc(ultimo),
        )
        for servicio, empresa_id, total, recientes, ultimo in await sesion.execute(consulta)
    ]


async def triar(
    sesion: AsyncSession, admin: Usuario, evento_id: int, datos: TriajeEntrada, ip: str | None
) -> EventoSeguridad:
    evento = await sesion.get(EventoSeguridad, evento_id)
    if not evento:
        raise NoEncontrado("Evento no encontrado")
    if datos.estado is not None:
        evento.estado_triaje = datos.estado
    if datos.nota is not None:
        evento.nota = datos.nota or None
    await auditar(
        sesion,
        accion="triaje_evento",
        recurso="evento_seguridad",
        usuario_id=admin.id,
        recurso_id=evento.id,
        ip=ip,
        detalle=str(evento.estado_triaje),
    )
    await sesion.commit()
    _difundir("triaje", evento)
    return evento


async def evento_por_incidente(sesion: AsyncSession, incidente_id: int) -> EventoSeguridad | None:
    return await sesion.scalar(
        select(EventoSeguridad).where(EventoSeguridad.incidente_id == incidente_id)
    )


async def crear_incidente(
    sesion: AsyncSession, admin: Usuario, evento_id: int, ip: str | None
) -> Incidente:
    evento = await sesion.get(EventoSeguridad, evento_id)
    if not evento:
        raise NoEncontrado("Evento no encontrado")
    if evento.incidente_id:
        raise Conflicto(f"El evento ya está en la incidencia #{evento.incidente_id}")

    nombre = NOMBRES_TIPO[evento.tipo]
    descripcion = (
        f"Incidencia abierta desde el evento de seguridad #{evento.id}.\n\n"
        f"Tipo: {nombre}\n"
        f"Origen: {evento.origen_ip}\n"
        f"Petición: {evento.metodo} {evento.ruta}\n"
        f"Servicio: {evento.servicio}\n"
        f"Fecha (UTC): {a_utc(evento.fecha):%Y-%m-%d %H:%M:%S}"
    )
    if evento.detalle:
        descripcion += f"\nDetalle: {evento.detalle}"

    incidente = Incidente(
        titulo=f"{nombre} desde {evento.origen_ip}"[:120],
        descripcion=descripcion,
        severidad=evento.severidad,
        categoria=CATEGORIA_DE_TIPO[evento.tipo],
        estado=Estado.abierto,
        reportante_id=admin.id,
        # La incidencia es del cliente dueño del sensor, no de quien la abre
        empresa_id=evento.empresa_id,
    )
    sesion.add(incidente)
    await sesion.flush()
    evento.incidente_id = incidente.id
    evento.estado_triaje = EstadoTriaje.revisado
    await auditar(
        sesion,
        accion="crear_incidente",
        recurso="incidente",
        usuario_id=admin.id,
        recurso_id=incidente.id,
        ip=ip,
        detalle=f"desde evento #{evento.id}",
    )
    await sesion.commit()
    _difundir("triaje", evento)  # el resto de paneles ven el enlace al ticket al momento
    return incidente
