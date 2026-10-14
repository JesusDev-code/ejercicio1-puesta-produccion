# syntax=docker/dockerfile:1

# Solo librería estándar de Python: no se instala ni una dependencia. La imagen es diminuta
# y la superficie de ataque, mínima.
FROM python:3.12-slim-bookworm

RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app

WORKDIR /app
COPY --chown=root:root *.py ./

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

USER app
EXPOSE 8000

# El señuelo no escribe nada ni necesita privilegios: va con el sistema de ficheros en solo lectura
CMD ["python", "arranque.py"]
