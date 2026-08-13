FROM node:22-bookworm-slim AS build

WORKDIR /app

COPY package*.json .npmrc ./
RUN npm ci --include=dev --no-audit --no-fund

COPY . .

ARG VITE_API_BASE_URL=http://localhost:8000
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

RUN npm run build

FROM nginx:1.27-alpine

COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
