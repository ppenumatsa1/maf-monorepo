#!/usr/bin/env sh
set -eu

API_BASE="${API_BASE-${VITE_API_BASE_URL-${VITE_API_BASE-}}}"
AG_UI_URL="${AG_UI_URL-${VITE_AG_UI_URL-}}"
COPILOTKIT_URL="${COPILOTKIT_URL-${VITE_COPILOTKIT_URL-}}"
NGINX_API_UPSTREAM="${NGINX_API_UPSTREAM-http://localhost:8000}"
export API_BASE
export AG_UI_URL
export COPILOTKIT_URL
export NGINX_API_UPSTREAM

envsubst '${API_BASE} ${AG_UI_URL} ${COPILOTKIT_URL}' \
  < /usr/share/nginx/html/env-config.template.js \
  > /usr/share/nginx/html/env-config.js

envsubst '${NGINX_API_UPSTREAM}' \
  < /etc/nginx/conf.d/default.conf.template \
  > /etc/nginx/conf.d/default.conf

exec nginx -g 'daemon off;'
