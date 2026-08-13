FROM node:20.19.0-alpine3.20 AS build

WORKDIR /app

COPY package*.json .npmrc ./
RUN for attempt in 1 2 3; do \
      npm ci --include=dev --no-audit && test -x node_modules/.bin/tsc && exit 0; \
      rm -rf node_modules; \
      [ "$attempt" = 3 ] && exit 1; \
      sleep "$attempt"; \
    done

COPY . .
RUN npm run build

FROM nginx:1.27-alpine AS runtime

RUN apk add --no-cache gettext

COPY nginx.conf /etc/nginx/conf.d/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

EXPOSE 5173

ENTRYPOINT ["/docker-entrypoint.sh"]
