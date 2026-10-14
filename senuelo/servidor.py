"""Señuelo (honeypot de registro).

Expuesto a internet, pero NO es vulnerable: no sirve ficheros, no ejecuta nada, no tiene
estado. Para cada petición que recibe, la clasifica y la registra en la API como un evento de
seguridad, y responde con una página genérica inofensiva. Internet lo sondea solo, sin parar:
de ahí sale el tráfico real que ve el panel.
"""

import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from clasificador import clasificar
from enviar import Enviador, env, esperar_api, ip_valida

_RESPUESTA = b"<!doctype html><title>No encontrado</title><h1>404 Not Found</h1>\n"
_MAX_RUTA = 4096


class Manejador(BaseHTTPRequestHandler):
    server_version = "nginx"  # no se anuncia que esto es un señuelo
    sys_version = ""
    protocol_version = "HTTP/1.1"
    enviador: Enviador

    def _registrar(self, metodo: str) -> None:
        ruta = self.path[:_MAX_RUTA]
        agente = self.headers.get("User-Agent")
        # X-Forwarded-For lo pone Traefik; el primer salto es la IP del cliente (manipulable,
        # pero es justo el dato que interesa). Si es basura, se usa la IP de la conexión.
        xff = (self.headers.get("X-Forwarded-For") or "").split(",")[0]
        tipo, severidad = clasificar(metodo, ruta, agente)
        self.enviador.encolar(
            {
                "origen_ip": ip_valida(xff, self.client_address[0]),
                "tipo": tipo,
                "severidad": severidad,
                "metodo": metodo,
                "ruta": ruta,
                "agente": agente,
                "servicio": "senuelo",
            }
        )

    def _responder(self, metodo: str) -> None:
        self._registrar(metodo)
        cuerpo = _RESPUESTA if metodo != "HEAD" else b""
        self.send_response(404)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(_RESPUESTA)))
        self.send_header("Connection", "close")
        self.end_headers()
        if cuerpo:
            self.wfile.write(cuerpo)

    # El cuerpo de la petición no se lee nunca: no interesa y evita leer megas de basura.
    def do_GET(self):
        self._responder("GET")

    def do_HEAD(self):
        self._responder("HEAD")

    def do_POST(self):
        self._responder("POST")

    do_PUT = do_DELETE = do_PATCH = do_OPTIONS = do_POST

    def log_message(self, *_args):
        pass  # el registro va a la API, no a stderr


def main() -> None:
    api = env("API_URL")
    enviador = Enviador(api, env("INGESTA_TOKEN"))
    esperar_api(api)
    enviador.iniciar()
    Manejador.enviador = enviador
    puerto = int(os.environ.get("PUERTO", "8000"))
    servidor = ThreadingHTTPServer(("0.0.0.0", puerto), Manejador)  # noqa: S104 - en contenedor
    print(f"[senuelo] escuchando en :{puerto}", flush=True)
    servidor.serve_forever()


if __name__ == "__main__":
    main()
