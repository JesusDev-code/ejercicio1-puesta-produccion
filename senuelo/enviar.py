"""Envío de eventos a la API, en lotes. Solo librería estándar."""

import ipaddress
import json
import os
import threading
import time
import urllib.error
import urllib.request


def ip_valida(candidata: str | None, respaldo: str) -> str:
    """Normaliza una IP; si no es válida (p. ej. un X-Forwarded-For manipulado), usa el respaldo.
    Así un valor basura no tira el lote entero por el 422 de la API."""
    for valor in (candidata, respaldo):
        if not valor:
            continue
        try:
            return str(ipaddress.ip_address(valor.strip()))
        except ValueError:
            continue
    return "0.0.0.0"  # noqa: S104 - marcador, no un bind


class Enviador:
    """Acumula eventos y los manda en lotes: por tamaño o cada `intervalo` segundos."""

    def __init__(
        self,
        api_url: str,
        token: str,
        tam_lote: int = 20,
        intervalo: float = 3.0,
        informe_cada: float = 300.0,
    ):
        self._url = api_url.rstrip("/") + "/eventos"
        self._token = token
        self._tam_lote = tam_lote
        self._intervalo = intervalo
        self._buffer: list[dict] = []
        self._lock = threading.Lock()
        self._parar = threading.Event()
        self._hilo = threading.Thread(target=self._bucle, daemon=True)
        # Resumen periódico en el log: sin él, un log vacío no distingue «todo bien» de
        # «no llega nada», porque solo se registraban los fallos
        self._informe_cada = informe_cada
        self._ultimo_informe = time.monotonic()
        self._entregados = 0
        self._perdidos = 0

    def iniciar(self) -> None:
        self._hilo.start()

    def encolar(self, evento: dict) -> None:
        with self._lock:
            self._buffer.append(evento)
            lote = self._tomar() if len(self._buffer) >= self._tam_lote else None
        if lote:
            self._enviar(lote)

    def _tomar(self) -> list[dict]:
        lote, self._buffer = self._buffer, []
        return lote

    def _bucle(self) -> None:
        while not self._parar.wait(self._intervalo):
            with self._lock:
                lote = self._tomar() if self._buffer else None
            if lote:
                self._enviar(lote)
            self._informar()

    def _informar(self) -> None:
        ahora = time.monotonic()
        if ahora - self._ultimo_informe < self._informe_cada:
            return
        minutos = round((ahora - self._ultimo_informe) / 60)
        with self._lock:
            entregados, perdidos = self._entregados, self._perdidos
            self._entregados = self._perdidos = 0
        self._ultimo_informe = ahora
        print(
            f"[enviar] {entregados} eventos entregados y {perdidos} perdidos "
            f"en los últimos {minutos} min",
            flush=True,
        )

    def _enviar(self, lote: list[dict]) -> None:
        cuerpo = json.dumps({"eventos": lote}).encode()
        peticion = urllib.request.Request(
            self._url,
            data=cuerpo,
            method="POST",
            headers={"Content-Type": "application/json", "X-Ingesta-Token": self._token},
        )
        try:
            with urllib.request.urlopen(peticion, timeout=5) as respuesta:  # noqa: S310 - URL fija de env
                respuesta.read()
            with self._lock:
                self._entregados += len(lote)
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            with self._lock:
                self._perdidos += len(lote)
            # Si la API no está disponible, se pierden estos eventos. Para una demo es aceptable;
            # no se reintenta para no acumular memoria sin límite.
            print(f"[enviar] no se pudieron enviar {len(lote)} eventos: {e}", flush=True)


def env(nombre: str, obligatorio: bool = True, por_defecto: str = "") -> str:
    valor = os.environ.get(nombre, por_defecto)
    if obligatorio and not valor:
        raise SystemExit(f"Falta la variable de entorno {nombre}")
    return valor


def esperar_api(api_url: str, intentos: int = 30) -> None:
    """Espera a que la API responda antes de empezar a mandar (arranque del compose)."""
    url = api_url.rstrip("/") + "/salud"
    for _ in range(intentos):
        try:
            with urllib.request.urlopen(url, timeout=3) as r:  # noqa: S310 - URL fija de env
                if r.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError, OSError):
            pass
        time.sleep(2)
    print("[enviar] la API no respondió a tiempo; se arranca igualmente", flush=True)
