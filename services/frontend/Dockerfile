# Build context = gốc repo:  docker compose --profile app up -d frontend  → http://localhost:3000
FROM node:22-alpine AS build
WORKDIR /app
COPY services/frontend/package.json services/frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY services/frontend/ ./
RUN npm run build

FROM nginx:1.27-alpine
COPY services/frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
