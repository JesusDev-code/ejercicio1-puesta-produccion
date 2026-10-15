"""Test del clasificador y de ip_valida (sin red). Se ejecuta con: python -m pytest senuelo/"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import pytest  # noqa: E402

from clasificador import clasificar  # noqa: E402
from enviar import ip_valida  # noqa: E402


@pytest.mark.parametrize(
    ("metodo", "ruta", "agente", "tipo", "severidad"),
    [
        ("GET", "/.env", "curl/8.5.0", "fichero_sensible", "critica"),
        ("GET", "/.git/config", "x", "fichero_sensible", "critica"),
        ("GET", "/../../../../etc/passwd", "x", "recorrido_rutas", "alta"),
        ("GET", "/?id=1' OR '1'='1", "x", "inyeccion", "alta"),
        ("GET", "/buscar?q=<script>alert(1)</script>", "x", "inyeccion", "alta"),
        ("GET", "/wp-login.php", "x", "sondeo_rutas", "media"),
        ("POST", "/api/login", "x", "fuerza_bruta", "media"),
        ("GET", "/cualquier-cosa", "sqlmap/1.8", "escaner", "baja"),
        ("GET", "/robots.txt", "Googlebot", "otro", "baja"),
    ],
)
def test_clasificar(metodo, ruta, agente, tipo, severidad):
    assert clasificar(metodo, ruta, agente) == (tipo, severidad)


def test_prioridad_recorrido_sobre_fichero():
    # Una ruta con ../ y .env a la vez se clasifica como recorrido (regla de mayor prioridad)
    assert clasificar("GET", "/../.env", "x")[0] == "recorrido_rutas"


def test_ip_valida():
    assert ip_valida("8.8.8.8", "1.2.3.4") == "8.8.8.8"
    assert ip_valida(" 203.0.113.9 ", "1.2.3.4") == "203.0.113.9"
    assert ip_valida("no-es-ip", "1.2.3.4") == "1.2.3.4"  # cae al respaldo
    assert ip_valida("x", "y") == "0.0.0.0"
    assert ip_valida(None, "::1") == "::1"


def test_informe_periodico_cuenta_entregados_y_perdidos(capsys):
    from enviar import Enviador

    enviador = Enviador("http://127.0.0.1:9", "x", informe_cada=0)
    enviador._entregados, enviador._perdidos = 7, 2
    enviador._informar()
    salida = capsys.readouterr().out
    assert "7 eventos entregados y 2 perdidos" in salida
    # El contador se reinicia tras cada informe
    assert enviador._entregados == 0
