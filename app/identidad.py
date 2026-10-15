"""Proveedor de identidad: Firebase Authentication.

Firebase guarda las contraseñas y emite los ID tokens; nosotros solo los verificamos. El rol, la
empresa y si la cuenta está activa siguen en NUESTRA base de datos y se leen en cada petición:
nunca se fían de custom claims que no hayamos puesto nosotros.

Todo el acceso a Firebase pasa por este módulo. Los tests sustituyen el proveedor por uno
falso con `establecer()`, así no salen nunca a la red.
"""

import asyncio
import base64
import binascii
import json
import logging
import urllib.error
import urllib.request
from typing import Protocol

import firebase_admin
from firebase_admin import auth, credentials

from app.config import obtener_configuracion

log = logging.getLogger(__name__)

_URL_LOGIN = "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key="


class EmailYaRegistrado(Exception):
    pass


class Identidad(Protocol):
    async def verificar(self, token: str) -> str | None:
        """uid del ID token, o None si no es válido, ha caducado o se ha revocado."""

    async def crear(self, email: str, contrasena: str) -> str: ...

    async def buscar(self, email: str) -> str | None: ...

    async def comprobar_contrasena(self, email: str, contrasena: str) -> bool: ...

    async def cambiar_contrasena(self, uid: str, nueva: str) -> None: ...

    async def activar(self, uid: str, activo: bool) -> None: ...

    async def revocar(self, uid: str) -> None:
        """Invalida los refresh tokens y, con `check_revoked`, los ID tokens ya emitidos."""


def _cargar_credenciales(valor: str) -> dict:
    """El JSON de la cuenta de servicio llega en base64 (o tal cual) desde el entorno."""
    texto = valor.strip()
    if not texto.startswith("{"):
        try:
            texto = base64.b64decode(texto, validate=True).decode()
        except (binascii.Error, UnicodeDecodeError) as e:
            raise RuntimeError("FIREBASE_CREDENCIALES no es base64 ni JSON") from e
    return json.loads(texto)


class IdentidadFirebase:
    def __init__(self, credenciales: str, api_key: str, proyecto: str = "", emulador: str = ""):
        if emulador:
            # Emulador local (E2E). ApplicationDefault se carga en diferido y nunca llega a usarse:
            # con el emulador, el cliente de Auth la sustituye por una credencial falsa
            self._app = firebase_admin.initialize_app(
                credentials.ApplicationDefault(), {"projectId": proyecto}, name="umbral"
            )
            self._url_login = f"http://{emulador}/identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key="
        else:
            self._app = firebase_admin.initialize_app(
                credentials.Certificate(_cargar_credenciales(credenciales)), name="umbral"
            )
            self._url_login = _URL_LOGIN
        self._api_key = api_key

    async def verificar(self, token: str) -> str | None:
        try:
            # check_revoked: una sesión revocada (cambio de contraseña, baja) deja de valer ya
            datos = await asyncio.to_thread(
                auth.verify_id_token, token, app=self._app, check_revoked=True
            )
        except (auth.InvalidIdTokenError, auth.UserDisabledError):
            # Incluye caducado y revocado, que son subclases de InvalidIdTokenError
            return None
        except (auth.CertificateFetchError, ValueError):
            log.warning("No se pudo verificar un ID token", exc_info=True)
            return None
        return datos.get("uid")

    async def crear(self, email: str, contrasena: str) -> str:
        try:
            usuario = await asyncio.to_thread(
                auth.create_user, email=email, password=contrasena, app=self._app
            )
        except auth.EmailAlreadyExistsError as e:
            raise EmailYaRegistrado(email) from e
        return usuario.uid

    async def buscar(self, email: str) -> str | None:
        try:
            usuario = await asyncio.to_thread(auth.get_user_by_email, email, app=self._app)
        except auth.UserNotFoundError:
            return None
        return usuario.uid

    async def comprobar_contrasena(self, email: str, contrasena: str) -> bool:
        """Firebase no ofrece «comprobar contraseña» en el Admin SDK: se hace un inicio de
        sesión contra su API REST y solo se mira si sale bien. El token que devuelve se descarta."""
        cuerpo = json.dumps(
            {"email": email, "password": contrasena, "returnSecureToken": False}
        ).encode()
        # URL fija (Google o el emulador local): no hay esquema ni destino controlado por el usuario
        peticion = urllib.request.Request(  # noqa: S310
            self._url_login + self._api_key,
            data=cuerpo,
            method="POST",
            headers={"Content-Type": "application/json"},
        )

        def enviar() -> bool:
            try:
                # URL fija de Google (https), no viene del usuario
                with urllib.request.urlopen(peticion, timeout=10):  # noqa: S310  # nosec B310
                    return True
            except urllib.error.HTTPError as e:
                if e.code == 400:  # credenciales incorrectas o demasiados intentos
                    return False
                raise

        return await asyncio.to_thread(enviar)

    async def cambiar_contrasena(self, uid: str, nueva: str) -> None:
        await asyncio.to_thread(auth.update_user, uid, password=nueva, app=self._app)

    async def activar(self, uid: str, activo: bool) -> None:
        await asyncio.to_thread(auth.update_user, uid, disabled=not activo, app=self._app)

    async def revocar(self, uid: str) -> None:
        await asyncio.to_thread(auth.revoke_refresh_tokens, uid, app=self._app)


_proveedor: Identidad | None = None


def identidad() -> Identidad:
    global _proveedor
    if _proveedor is None:
        config = obtener_configuracion()
        emulador = config.firebase_auth_emulator_host
        if not config.firebase_credenciales and not emulador:
            raise RuntimeError("Falta FIREBASE_CREDENCIALES: no se puede verificar a nadie")
        _proveedor = IdentidadFirebase(
            config.firebase_credenciales,
            config.firebase_api_key,
            config.firebase_project_id,
            emulador,
        )
    return _proveedor


def establecer(proveedor: Identidad | None) -> None:
    """Para los tests: sustituye Firebase por un proveedor falso."""
    global _proveedor
    _proveedor = proveedor
