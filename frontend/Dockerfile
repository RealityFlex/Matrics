#
# Stage 1 — сборка фронтенда
#
FROM node:20-alpine AS build

WORKDIR /app

# Устанавливаем зависимости
COPY package*.json ./
RUN npm ci --no-audit --no-fund

# Собираем проект
COPY . .
RUN npm run build

#
# Stage 2 — лёгкий nginx со статикой
#
FROM nginx:1.25-alpine

ENV NGINX_ENVSUBST_OUTPUT_DIR=/etc/nginx/conf.d

# Копируем собранную статику
COPY --from=build /app/dist /usr/share/nginx/html

# Конфигурация nginx с поддержкой SPA и проксированием API на gateway
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]

