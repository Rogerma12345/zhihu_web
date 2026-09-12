# syntax=docker/dockerfile:1.7

FROM --platform=$BUILDPLATFORM node:22-bookworm-slim AS builder

WORKDIR /app

COPY package.json package-lock.json ./

RUN mkdir -p src/fonts \
    && npm ci --no-audit --no-fund

COPY . .

RUN npm run build \
    && test -f /app/html/index.html \
    && test -f /app/html/service-worker.js

FROM nginx:alpine-slim

LABEL org.opencontainers.image.source="https://github.com/Rogerma12345/zhihu_web"

RUN rm -rf /usr/share/nginx/html/*

COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf

COPY --from=builder /app/html/ /usr/share/nginx/html/zhihu_web/

EXPOSE 80