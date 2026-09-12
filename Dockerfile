FROM nginx:alpine-slim

LABEL org.opencontainers.image.source="https://github.com/Rogerma12345/zhihu_web"

RUN rm -rf /usr/share/nginx/html/*

COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
COPY html/ /usr/share/nginx/html/zhihu_web/

EXPOSE 80
