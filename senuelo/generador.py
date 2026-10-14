"""Generador de eventos de DEMOSTRACIÓN.

No ataca a nadie: fabrica registros de telemetría (líneas de log) que imitan el ruido de
sondeo que cualquier servicio recibe de internet, y los manda a la API para que el panel
tenga datos en vivo durante una demo o cuando el señuelo está tranquilo. Cada registro pasa
por el mismo clasificador que el tráfico real, así las etiquetas son coherentes.
"""

import os
import random
import time

from clasificador import clasificar
from enviar import Enviador, env, esperar_api

# Catálogo de rutas y agentes que de verdad aparecen en los logs de un servidor público.
_RUTAS = [
    "/.env",
    "/.git/config",
    "/wp-login.php",
    "/wp-config.php.bak",
    "/backup.sql",
    "/administrator/index.php",
    "/phpmyadmin/",
    "/.aws/credentials",
    "/admin",
    "/?id=1' OR '1'='1",
    "/search?q=<script>alert(1)</script>",
    "/../../../../etc/passwd",
    "/api/login",
    "/user/login",
    "/.well-known/security.txt",
    "/cgi-bin/luci",
    "/solr/admin/info/system",
    "/boaform/admin/formLogin",
    "/index.php?page=../../etc/passwd",
    "/vendor/phpunit/phpunit/src/Util/PHP/eval-stdin.php",
    "/robots.txt",
    "/favicon.ico",
    "/sitemap.xml",
    "/.git/HEAD",
    "/config.json",
    "/server-status",
]
_METODOS = ["GET", "GET", "GET", "POST", "HEAD"]  # GET domina, como en la realidad
_AGENTES = [
    "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
    "curl/8.5.0",
    "python-requests/2.31.0",
    "Go-http-client/1.1",
    "sqlmap/1.8",
    "Nikto/2.5.0",
    "masscan/1.3",
    "Mozilla/5.0 (X11; Linux x86_64) Gecko/20100101 Firefox/120.0",
    "zgrab/0.x",
    "Nuclei - Open-source project (github.com/projectdiscovery/nuclei)",
]
# Rangos públicos de ejemplo (RFC 5737 + algún rango real de escaneo conocido) para la IP origen
_PREFIJOS = ["203.0.113", "198.51.100", "192.0.2", "185.220.101", "45.148.10", "89.248.165"]


def _ip() -> str:
    return f"{random.choice(_PREFIJOS)}.{random.randint(1, 254)}"


def _evento(empresas: list[str]) -> dict:
    metodo = random.choice(_METODOS)
    ruta = random.choice(_RUTAS)
    agente = random.choice(_AGENTES)
    tipo, severidad = clasificar(metodo, ruta, agente)
    evento = {
        "origen_ip": _ip(),
        "tipo": tipo,
        "severidad": severidad,
        "metodo": metodo,
        "ruta": ruta,
        "agente": agente,
        "servicio": "generador-demo",
    }
    if empresas:
        evento["empresa"] = random.choice(empresas)
    return evento


def main() -> None:
    api = env("API_URL")
    enviador = Enviador(api, env("INGESTA_TOKEN"), tam_lote=5, intervalo=2.0)
    esperar_api(api)
    enviador.iniciar()

    minimo = float(os.environ.get("INTERVALO_MIN", "1.5"))
    maximo = float(os.environ.get("INTERVALO_MAX", "6.0"))
    # Códigos de cliente separados por comas: cada evento se atribuye a uno al azar
    empresas = [c.strip() for c in os.environ.get("EMPRESAS", "").split(",") if c.strip()]
    # Semilla no criptográfica: es una demo, no hay nada que proteger
    rng = random.Random()  # noqa: S311
    print(f"[generador] emitiendo eventos de demo cada {minimo}-{maximo}s", flush=True)
    while True:
        for _ in range(rng.randint(1, 3)):
            enviador.encolar(_evento(empresas))
        time.sleep(rng.uniform(minimo, maximo))


if __name__ == "__main__":
    main()
