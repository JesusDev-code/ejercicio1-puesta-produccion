"""Difusión en memoria de eventos nuevos a los paneles abiertos (SSE).

Vive en el proceso: funciona porque la API corre con un único worker (igual que el rate
limit). Con varias réplicas habría que pasarlo a Redis pub/sub."""

import asyncio


class Difusor:
    def __init__(self, capacidad: int = 200):
        self._colas: set[asyncio.Queue[str]] = set()
        self._capacidad = capacidad

    def suscribir(self) -> asyncio.Queue[str]:
        cola: asyncio.Queue[str] = asyncio.Queue(maxsize=self._capacidad)
        self._colas.add(cola)
        return cola

    def baja(self, cola: asyncio.Queue[str]) -> None:
        self._colas.discard(cola)

    def publicar(self, dato: str) -> None:
        for cola in list(self._colas):
            try:
                cola.put_nowait(dato)
            except asyncio.QueueFull:
                # Un cliente lento pierde eventos; nunca frena la ingesta ni a los demás
                pass

    @property
    def suscriptores(self) -> int:
        return len(self._colas)


difusor = Difusor()
