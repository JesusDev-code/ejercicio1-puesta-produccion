"""Reglas de detección, al estilo de un WAF: dada una petición, ¿qué clase de sondeo es?

Es puramente defensivo: solo clasifica texto que ya ha llegado. No ataca nada, no ejecuta
nada. Lo usan por igual el señuelo (con tráfico real) y el generador (con tráfico de demo),
así que un evento inventado se etiqueta con el mismo criterio que uno real.
"""

import re

# Orden de prioridad: la primera regla que coincide manda. Cada tupla es (tipo, severidad).
_REGLAS: list[tuple[re.Pattern[str], str, str]] = [
    (
        re.compile(r"(\.\./|\.\.%2f|%2e%2e[/\\]|/etc/passwd|boot\.ini|\\windows\\win)", re.I),
        "recorrido_rutas",
        "alta",
    ),
    (
        re.compile(
            r"(\bunion\b\s+\bselect\b|'\s*or\s*'?1'?\s*=\s*'?1|<script|%3cscript|"
            r"\bor\b\s+1\s*=\s*1|sleep\(\d+\)|benchmark\(|\bwaitfor\b\s+delay)",
            re.I,
        ),
        "inyeccion",
        "alta",
    ),
    (
        re.compile(
            r"(/\.env|/\.git|\.htpasswd|wp-config\.php|id_rsa|\.aws/credentials|"
            r"\.(bak|sql|sqlite|pem|key|p12|backup)(\b|$)|/backup|/dump)",
            re.I,
        ),
        "fichero_sensible",
        "critica",
    ),
    (
        re.compile(
            r"/(wp-login|wp-admin|administrator|phpmyadmin|pma|manager/html|"
            r"cgi-bin|boaform|solr|jenkins|\.well-known/.*admin)",
            re.I,
        ),
        "sondeo_rutas",
        "media",
    ),
]

_LOGIN = re.compile(r"/(login|signin|sign-in|auth|session|admin/login|api/login|user/login)", re.I)
_ESCANER = re.compile(
    r"(nikto|sqlmap|nmap|masscan|zgrab|zmap|nuclei|dirbuster|gobuster|feroxbuster|wpscan|"
    r"acunetix|nessus|openvas|censys|shodan|python-requests|go-http-client|libwww-perl|curl/)",
    re.I,
)


def clasificar(metodo: str, ruta: str, agente: str | None) -> tuple[str, str]:
    """Devuelve (tipo, severidad) para la petición. Nunca lanza: todo cae en 'otro'."""
    for patron, tipo, severidad in _REGLAS:
        if patron.search(ruta):
            return tipo, severidad
    if metodo == "POST" and _LOGIN.search(ruta):
        return "fuerza_bruta", "media"
    if agente and _ESCANER.search(agente):
        return "escaner", "baja"
    return "otro", "baja"
