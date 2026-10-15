"""Datos ficticios para enseñar la aplicación: `python -m app.cli sembrar-demo`.

- Idempotente: si ya hay datos de demo, no hace nada.
- Las cuentas de demo no existen en Firebase (no tienen uid): no se puede entrar con ellas.
  Solo sirven para que haya reportantes, analistas e historial.
- Dominio ficticio: ningún correo se envía nunca a estas direcciones.
- Los clientes del MSSP se crean aparte y también son idempotentes: en una BD sembrada antes de
  que existieran las empresas, se crean y se reparten los usuarios de demo que no tengan."""

import secrets
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modelos import (
    Categoria,
    Empresa,
    Estado,
    Incidente,
    RegistroAuditoria,
    Rol,
    Severidad,
    Usuario,
    ahora,
)

DOMINIO = "demo-incidentes.es"

# (código, nombre, sector). El código es el que declaran los sensores en EMPRESA/EMPRESAS
EMPRESAS = [
    ("transportes-ibarra", "Transportes Ibarra", "Logística"),
    ("clinica-solana", "Clínica Solana", "Sanidad"),
    ("hotel-mirador", "Hotel Mirador", "Hostelería"),
]

# (email, rol, activo, días desde el alta, empresa). Sin empresa = personal del MSSP
USUARIOS = [
    ("a.ruiz", Rol.analista, True, 12, None),
    ("m.soto", Rol.analista, True, 12, None),
    ("l.vega", Rol.analista, False, 10, None),
    ("p.lopez", Rol.usuario, True, 9, "transportes-ibarra"),
    ("c.navarro", Rol.usuario, True, 8, "transportes-ibarra"),
    ("j.moreno", Rol.usuario, True, 6, "clinica-solana"),
    ("becario", Rol.usuario, True, 3, "hotel-mirador"),
]

# (título, descripción, severidad, categoría, estado, reportante, analista, notas, días atrás)
INCIDENTES = [
    (
        "Correo que suplanta a RR. HH. con enlace a formulario de credenciales",
        "A las 09:12 varios empleados han recibido un correo con remitente «Recursos Humanos» y "
        "asunto «Actualización de nóminas octubre». El enlace lleva a una página que imita el "
        "portal del empleado y pide usuario y contraseña.\n\nAl menos una persona de Contabilidad "
        "ha introducido sus credenciales antes de darse cuenta.",
        Severidad.critica,
        Categoria.phishing,
        Estado.en_analisis,
        "p.lopez",
        "a.ruiz",
        "[09:58] Dominio del enlace registrado hace 2 días. Bloqueado en el proxy.\n"
        "[10:14] Credenciales de la usuaria de Contabilidad reseteadas y sesiones revocadas.\n"
        "[10:30] Pendiente: buscar el mismo remitente en el resto de buzones.",
        0,
    ),
    (
        "Portátil de comercial con proceso desconocido en el arranque",
        "El antivirus no salta, pero al arrancar aparece un proceso «svchostt.exe» que consume CPU "
        "y abre conexiones salientes por el puerto 443 a una IP que no reconozco.",
        Severidad.alta,
        Categoria.malware,
        Estado.abierto,
        "c.navarro",
        None,
        None,
        0,
    ),
    (
        "Inicios de sesión VPN desde país no habitual",
        "El concentrador VPN registra tres inicios de sesión correctos de mi cuenta desde Rumanía "
        "esta madrugada. Yo estaba en Cádiz y no tenía el portátil encendido.",
        Severidad.alta,
        Categoria.acceso_no_autorizado,
        Estado.en_analisis,
        "j.moreno",
        "m.soto",
        "Cuenta bloqueada. MFA no estaba activado para este usuario: abrir tarea para forzarlo "
        "en todo el departamento.",
        1,
    ),
    (
        "Hoja de cálculo con datos de clientes compartida públicamente",
        "Un enlace público a una hoja con nombres, DNI y teléfonos de clientes aparece en un foro. "
        "La hoja es nuestra: la creó el equipo de Ventas para una campaña.",
        Severidad.critica,
        Categoria.fuga_datos,
        Estado.resuelto,
        "p.lopez",
        "a.ruiz",
        "Enlace revocado. 1.240 registros expuestos 36 h. Notificación a la AEPD preparada "
        "por el DPO dentro de plazo (art. 33 RGPD).",
        2,
    ),
    (
        "Picos de tráfico en la web corporativa en horario nocturno",
        "Entre las 02:00 y las 04:00 la web tarda más de 10 s en responder. Las gráficas del "
        "balanceador muestran picos de 20 veces el tráfico normal.",
        Severidad.media,
        Categoria.denegacion_servicio,
        Estado.abierto,
        "j.moreno",
        None,
        None,
        3,
    ),
    (
        "Adjunto .iso recibido de un proveedor habitual",
        "Correo del proveedor de material de oficina con una «factura» en formato .iso. El "
        "proveedor dice que no lo ha enviado.",
        Severidad.media,
        Categoria.phishing,
        Estado.cerrado,
        "c.navarro",
        "m.soto",
        "Cuenta del proveedor comprometida. Regla de correo para bloquear adjuntos .iso/.img.",
        4,
    ),
    (
        "Cuenta de becario con permisos de administración local",
        "Revisando el portátil del nuevo becario veo que su cuenta está en el grupo de "
        "administradores locales. No debería.",
        Severidad.baja,
        Categoria.acceso_no_autorizado,
        Estado.cerrado,
        "becario",
        "a.ruiz",
        "Error en la plantilla de alta. Corregida y revisados los últimos 20 equipos.",
        5,
    ),
    (
        "Impresora de la planta 2 responde en puertos no documentados",
        "Un escaneo rutinario muestra la impresora con los puertos 23 y 9100 abiertos y la "
        "página de administración sin contraseña.",
        Severidad.baja,
        Categoria.otro,
        Estado.resuelto,
        "j.moreno",
        "m.soto",
        "Telnet desactivado, contraseña de administración cambiada, firmware actualizado.",
        6,
    ),
    (
        "USB encontrado en el aparcamiento conectado a un equipo de recepción",
        "La recepcionista encontró un pendrive en el aparcamiento y lo conectó para ver de quién "
        "era. Al abrirlo solo había un acceso directo.",
        Severidad.alta,
        Categoria.malware,
        Estado.en_analisis,
        "c.navarro",
        "a.ruiz",
        "Equipo aislado de la red. Volcado de memoria hecho. El .lnk lanza PowerShell codificado.",
        1,
    ),
    (
        "Contraseñas en texto claro en un repositorio interno",
        "En el repositorio de scripts de despliegue hay un fichero config.ini con la contraseña "
        "del usuario de la base de datos de producción.",
        Severidad.alta,
        Categoria.fuga_datos,
        Estado.abierto,
        "p.lopez",
        None,
        None,
        0,
    ),
    (
        "SMS que suplanta al banco pidiendo verificar la cuenta",
        "Varios compañeros han recibido el mismo SMS con un enlace acortado. No es correo, pero "
        "lo reporto por si afecta a cuentas de empresa.",
        Severidad.baja,
        Categoria.phishing,
        Estado.abierto,
        "becario",
        None,
        None,
        2,
    ),
    (
        "Ataque de fuerza bruta contra el formulario de acceso de la intranet",
        "El registro de la intranet muestra miles de intentos de login fallidos desde un rango "
        "de IPs en pocos minutos.",
        Severidad.media,
        Categoria.acceso_no_autorizado,
        Estado.resuelto,
        "j.moreno",
        "m.soto",
        "Rate limit añadido en el proxy y rango bloqueado. Ninguna cuenta comprometida.",
        7,
    ),
]

IP_ANALISTAS = "10.0.4.21"
IP_USUARIOS = "10.0.6.33"


def _email(nombre: str) -> str:
    return f"{nombre}@{DOMINIO}"


async def ya_sembrado(sesion: AsyncSession) -> bool:
    existe = await sesion.scalar(
        select(Usuario.id).where(Usuario.email.endswith(f"@{DOMINIO}")).limit(1)
    )
    return existe is not None


async def sembrar_empresas(sesion: AsyncSession) -> dict[str, int]:
    """Crea las que falten y reparte a los usuarios de demo que aún no tengan empresa (y sus
    incidencias). Devuelve código -> id."""
    existentes = {e.codigo: e for e in await sesion.scalars(select(Empresa))}
    for codigo, nombre, sector in EMPRESAS:
        if codigo not in existentes:
            existentes[codigo] = Empresa(codigo=codigo, nombre=nombre, sector=sector)
            sesion.add(existentes[codigo])
    await sesion.flush()
    ids = {codigo: e.id for codigo, e in existentes.items()}

    for nombre, _, _, _, empresa in USUARIOS:
        if not empresa:
            continue
        usuario = await sesion.scalar(select(Usuario).where(Usuario.email == _email(nombre)))
        if usuario and usuario.empresa_id is None:
            usuario.empresa_id = ids[empresa]
            for inc in await sesion.scalars(
                select(Incidente).where(
                    Incidente.reportante_id == usuario.id, Incidente.empresa_id.is_(None)
                )
            ):
                inc.empresa_id = ids[empresa]
    return ids


async def sembrar_demo(sesion: AsyncSession) -> bool:
    """Devuelve False si ya había datos de demo (las empresas se completan igualmente)."""
    if await ya_sembrado(sesion):
        await sembrar_empresas(sesion)
        await sesion.commit()
        return False

    empresas = await sembrar_empresas(sesion)

    momento = ahora()
    auditoria: list[RegistroAuditoria] = []

    def registro(accion, recurso, usuario_id, recurso_id, fecha, ip=IP_USUARIOS, detalle=None):
        auditoria.append(
            RegistroAuditoria(
                usuario_id=usuario_id,
                accion=accion,
                recurso=recurso,
                recurso_id=recurso_id,
                ip=ip,
                detalle=detalle,
                fecha=fecha,
            )
        )

    usuarios: dict[str, Usuario] = {}
    for nombre, rol, activo, dias, empresa in USUARIOS:
        u = Usuario(
            email=_email(nombre),
            rol=rol,
            empresa_id=empresas[empresa] if empresa else None,
            activo=activo,
            creado_en=momento - timedelta(days=dias),
        )
        sesion.add(u)
        usuarios[nombre] = u
    await sesion.flush()

    for nombre, rol, activo, dias, _ in USUARIOS:
        u = usuarios[nombre]
        alta = momento - timedelta(days=dias)
        registro("registro", "usuario", u.id, u.id, alta)
        if rol != Rol.usuario:
            registro(
                "cambio_rol",
                "usuario",
                None,
                u.id,
                alta + timedelta(hours=2),
                ip=None,
                detalle=f"usuario -> {rol}",
            )
        if not activo:
            registro("desactivar_usuario", "usuario", None, u.id, alta + timedelta(days=3), ip=None)

    for titulo, desc, sev, cat, estado, rep, ana, notas, dias in INCIDENTES:
        creado = momento - timedelta(days=dias, hours=secrets.randbelow(8) + 1)
        inc = Incidente(
            titulo=titulo,
            descripcion=desc,
            severidad=sev,
            categoria=cat,
            estado=estado,
            reportante_id=usuarios[rep].id,
            empresa_id=usuarios[rep].empresa_id,
            analista_id=usuarios[ana].id if ana else None,
            notas_internas=notas,
            creado_en=creado,
            actualizado_en=creado + timedelta(minutes=45) if ana else creado,
        )
        sesion.add(inc)
        await sesion.flush()

        registro("crear_incidente", "incidente", usuarios[rep].id, inc.id, creado)
        if ana:
            analista = usuarios[ana]
            registro(
                "asignar_incidente",
                "incidente",
                None,
                inc.id,
                creado + timedelta(minutes=10),
                ip=None,
                detalle=f"analista #{analista.id}",
            )
            camino = [Estado.abierto, Estado.en_analisis, Estado.resuelto, Estado.cerrado]
            for i in range(1, camino.index(estado) + 1):
                registro(
                    "cambio_estado",
                    "incidente",
                    analista.id,
                    inc.id,
                    creado + timedelta(minutes=15 + 10 * i),
                    ip=IP_ANALISTAS,
                    detalle=f"{camino[i - 1]} -> {camino[i]}",
                )
            if notas:
                registro(
                    "editar_notas",
                    "incidente",
                    analista.id,
                    inc.id,
                    creado + timedelta(minutes=40),
                    ip=IP_ANALISTAS,
                )

    # Alertas de seguridad para que la auditoría tenga algo que enseñar
    p_lopez = usuarios["p.lopez"]
    registro(
        "login_fallido",
        "usuario",
        None,
        None,
        momento - timedelta(hours=5),
        ip="185.220.101.7",
        detalle="email inexistente",
    )
    registro("login_fallido", "usuario", p_lopez.id, None, momento - timedelta(hours=4, minutes=58))
    registro("login", "usuario", p_lopez.id, None, momento - timedelta(hours=4, minutes=57))
    registro(
        "reutilizacion_token",
        "token_refresco",
        usuarios["j.moreno"].id,
        None,
        momento - timedelta(hours=3),
        ip="185.220.101.7",
        detalle="familia revocada",
    )
    registro("logout", "usuario", usuarios["m.soto"].id, None, momento - timedelta(hours=1))

    sesion.add_all(auditoria)
    await sesion.commit()
    return True
