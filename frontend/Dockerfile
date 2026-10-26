# 前端镜像：Node 构建 -> nginx 托管静态文件
# 构建上下文为 his-mvp 根目录
FROM node:18-alpine AS build
WORKDIR /app
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./

# VITE_API_BASE 在构建时注入（Vite 编译期变量）
ARG VITE_API_BASE=http://localhost:8000
ENV VITE_API_BASE=$VITE_API_BASE
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
