# Builds the frontend and serves it with Caddy. Build context is the repository root.
FROM node:22-alpine AS build
WORKDIR /src
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npx vite build

FROM caddy:2-alpine
COPY deploy/Caddyfile /etc/caddy/Caddyfile
COPY deploy/caddy/tls.dev.caddy /etc/caddy/tls.caddy
COPY --from=build /src/dist /srv
