# syntax=docker/dockerfile:1

# ---- Etapa 1: build de Angular ----
FROM node:22-alpine AS builder

WORKDIR /app

# Solo los manifiestos: la capa de dependencias se cachea mientras no cambie el lock
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci --no-audit --no-fund

COPY angular.json tsconfig.json tsconfig.app.json ./
COPY public ./public
COPY src ./src
RUN npx ng build

# ---- Etapa 2: solo estáticos y nginx sin privilegios (uid 101, puerto 8080) ----
FROM nginxinc/nginx-unprivileged:1.31.6-alpine

COPY --chown=root:root nginx/default.conf /etc/nginx/conf.d/default.conf
COPY --chown=root:root nginx/cabeceras-seguridad.conf /etc/nginx/cabeceras-seguridad.conf
# Ficheros de root y de solo lectura para el proceso nginx
COPY --from=builder --chown=root:root /app/dist/web/browser /usr/share/nginx/html

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["wget", "-q", "--spider", "http://127.0.0.1:8080/"]
