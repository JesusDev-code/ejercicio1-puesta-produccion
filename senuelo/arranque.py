"""Punto de entrada único. MODO elige el papel: señuelo o generador de demo."""

import os
import sys

MODO = os.environ.get("MODO", "senuelo")

if MODO == "senuelo":
    from servidor import main
elif MODO == "generador":
    from generador import main
else:
    sys.exit(f"MODO desconocido: {MODO!r} (usa 'senuelo' o 'generador')")

if __name__ == "__main__":
    main()
