"""Inicio y cierre de sesión.

Las credenciales las comprueba Firebase en el navegador, así que la API no ve los intentos
fallidos (los registra y frena Firebase). Lo que sí registra es quién entra y quién sale: el
front avisa con su ID token recién emitido, y eso queda en la auditoría como antes.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.modelos import Usuario
from app.servicios.auditoria import auditar


async def registrar_entrada(sesion: AsyncSession, usuario: Usuario, ip: str | None) -> None:
    await auditar(sesion, accion="login", recurso="usuario", usuario_id=usuario.id, ip=ip)
    await sesion.commit()


async def registrar_salida(sesion: AsyncSession, usuario: Usuario, ip: str | None) -> None:
    await auditar(sesion, accion="logout", recurso="usuario", usuario_id=usuario.id, ip=ip)
    await sesion.commit()
