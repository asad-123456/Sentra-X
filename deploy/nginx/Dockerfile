# Build context is the repo root (see docker-compose.yml)
FROM node:22-alpine AS build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund --fetch-timeout=180000 --fetch-retries=10
COPY frontend/ .
# A non-empty VITE_API_BASE_URL switches the UI from mock data to the live API.
# nginx serves the UI and proxies /api on the same origin, so there is no CORS to set up.
ARG VITE_API_BASE_URL=https://localhost:8443
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
# vite build only; the separate `tsc -b` type check is a lint step, not needed to produce the site
RUN npx vite build

FROM nginx:1.27-alpine
# Self-signed certificate generated at image build time.
# LAB/DEMO USE ONLY — a new cert is generated on every image rebuild, breaking
# browser trust after rebuilds. For production, remove this RUN block and mount
# a real cert via a Docker volume or secret into /etc/nginx/certs/.
RUN apk add --no-cache openssl curl \
 && mkdir -p /etc/nginx/certs \
 && openssl req -x509 -nodes -newkey rsa:2048 -days 365 \
      -keyout /etc/nginx/certs/sentrax.key \
      -out /etc/nginx/certs/sentrax.crt \
      -subj "/CN=localhost" \
      -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"
COPY deploy/nginx/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
