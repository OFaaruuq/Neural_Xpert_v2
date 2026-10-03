#!/usr/bin/env bash
# Production setup for Neural Xpert on Ubuntu.
# Installs PostgreSQL, creates the database, builds the virtualenv,
# migrates and seeds, then starts Gunicorn behind Nginx.
#
# Run as root from the cloned repository:
#   cd /root/Neural_Xpert_v2
#   bash deploy/setup-ubuntu.sh
#
# Optional environment overrides:
#   DOMAIN=neuralxpert.com bash deploy/setup-ubuntu.sh

set -euo pipefail

APP_DIR="${APP_DIR:-/var/www/neuralxpert}"
DOMAIN="${DOMAIN:-neuralxpert.com}"
DB_NAME="${DB_NAME:-neuralxpert}"
DB_USER="${DB_USER:-neuralxpert}"
CERTBOT_EMAIL="${CERTBOT_EMAIL:-partnerships@neuralxpert.com}"
CREDENTIALS_FILE="${CREDENTIALS_FILE:-/root/neuralxpert-credentials.txt}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run this script as root."
  exit 1
fi

if [[ -f "${PWD}/wsgi.py" && -d "${PWD}/app" ]]; then
  SOURCE_DIR="${SOURCE_DIR:-$PWD}"
elif [[ -f /root/Neural_Xpert_v2/wsgi.py ]]; then
  SOURCE_DIR="${SOURCE_DIR:-/root/Neural_Xpert_v2}"
else
  echo "Run this script from the Neural_Xpert_v2 repository."
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive

echo "Installing system packages..."
apt-get update
apt-get install -y \
  python3 \
  python3-venv \
  python3-pip \
  postgresql \
  postgresql-contrib \
  nginx \
  openssl \
  rsync \
  ca-certificates

if [[ ! -f "${SOURCE_DIR}/migrations/env.py" ]]; then
  echo "Restoring the PostgreSQL migrations folder from git..."
  git -C "${SOURCE_DIR}" checkout HEAD -- migrations
fi
if [[ ! -f "${SOURCE_DIR}/migrations/env.py" || ! -d "${SOURCE_DIR}/migrations/versions" ]]; then
  echo "migrations/ is missing in ${SOURCE_DIR}. PostgreSQL schema cannot be created."
  exit 1
fi

COMMIT="$(git -C "${SOURCE_DIR}" rev-parse --short HEAD 2>/dev/null || echo unknown)"
echo "Deploying commit ${COMMIT} from ${SOURCE_DIR}"
echo "Copying the application to ${APP_DIR}..."
install -d -m 755 "${APP_DIR}"
rsync -a --delete \
  --exclude '.git/' \
  --exclude '.venv/' \
  --exclude 'venv/' \
  --exclude 'vevn/' \
  --exclude 'instance/' \
  --exclude '__pycache__/' \
  --exclude '.pytest_cache/' \
  --exclude '.env' \
  --exclude 'app/static/uploads/' \
  "${SOURCE_DIR}/" "${APP_DIR}/"

if [[ ! -f "${APP_DIR}/app/static/img/logo-neural-xpert.png" ]] \
  || ! grep -q "brand.header" "${APP_DIR}/app/templates/includes/navbar.html" \
  || ! grep -q "logo-neural-xpert.png" "${APP_DIR}/app/brand.py"; then
  echo "The public logo was not copied into ${APP_DIR}."
  echo "The navbar must use brand.header, and brand.py must keep img/logo-neural-xpert.png."
  echo "Run: cd ${SOURCE_DIR} && git pull origin main && git log -1 --oneline"
  exit 1
fi

if [[ ! -f "${APP_DIR}/app/ai_support.py" ]] \
  || [[ ! -f "${APP_DIR}/app/static/js/ask-ai.js" ]] \
  || [[ ! -f "${APP_DIR}/app/static/css/ask-ai.css" ]] \
  || [[ ! -f "${APP_DIR}/app/templates/includes/ask_ai.html" ]] \
  || [[ ! -f "${APP_DIR}/app/static/img/bg/nx-hero.mp4" ]] \
  || [[ -f "${APP_DIR}/app/static/img/bg/aior.mp4" ]] \
  || ! grep -q "nx-hero.mp4" "${APP_DIR}/app/templates/main/home.html" \
  || ! grep -q 'DEFAULT_LABEL = "ASK AI"' "${APP_DIR}/app/ai_support.py"; then
  echo "ASK AI or the homepage video was not copied into ${APP_DIR}."
  echo "The hero file must be img/bg/nx-hero.mp4, and the public button must be named ASK AI."
  echo "Run: cd ${SOURCE_DIR} && git pull origin main && git log -1 --oneline"
  exit 1
fi

install -d -o www-data -g www-data -m 750 "${APP_DIR}/instance"
install -d -o www-data -g www-data -m 750 "${APP_DIR}/instance/uploads"
install -d -o www-data -g www-data -m 750 "${APP_DIR}/instance/uploads/media"
install -d -o www-data -g www-data -m 755 "${APP_DIR}/app/static/uploads"
chown -R www-data:www-data "${APP_DIR}/instance" "${APP_DIR}/app/static/uploads"

env_get() {
  local line value
  line="$(grep -E "^${2}=" "${1}" | tail -n 1 || true)"
  value="${line#*=}"
  if [[ "${value}" == \"*\" && "${value}" == *\" ]]; then
    value="${value:1:${#value}-2}"
  elif [[ "${value}" == \'*\' && "${value}" == *\' ]]; then
    value="${value:1:${#value}-2}"
  fi
  printf '%s' "${value}"
}

env_set() {
  local tmp
  tmp="$(mktemp)"
  if [[ -f "${1}" ]]; then
    grep -v -E "^${2}=" "${1}" > "${tmp}" || true
  fi
  printf '%s="%s"\n' "${2}" "${3}" >> "${tmp}"
  mv "${tmp}" "${1}"
}

systemctl enable postgresql
systemctl start postgresql

echo "Ensuring the PostgreSQL role and database..."
ENV_FILE="${APP_DIR}/.env"
CURRENT_URL=""
if [[ -f "${ENV_FILE}" ]]; then
  CURRENT_URL="$(env_get "${ENV_FILE}" DATABASE_URL)"
fi

if [[ -z "${CURRENT_URL}" || "${CURRENT_URL}" != postgresql* ]]; then
  DB_PASSWORD="$(openssl rand -hex 24)"
  sudo -u postgres psql -v ON_ERROR_STOP=1 <<SQL
DO \$\$
BEGIN
   IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '${DB_USER}') THEN
      CREATE ROLE ${DB_USER} LOGIN PASSWORD '${DB_PASSWORD}';
   ELSE
      ALTER ROLE ${DB_USER} WITH LOGIN PASSWORD '${DB_PASSWORD}';
   END IF;
END
\$\$;
SQL
  DATABASE_URL="postgresql+psycopg://${DB_USER}:${DB_PASSWORD}@localhost:5432/${DB_NAME}"
  echo "PostgreSQL URL written. MySQL and SQLite URLs are not used."
else
  DATABASE_URL="${CURRENT_URL}"
  echo "Keeping the existing PostgreSQL DATABASE_URL."
fi

if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname = '${DB_NAME}'" | grep -q 1; then
  sudo -u postgres createdb --owner="${DB_USER}" "${DB_NAME}"
fi
sudo -u postgres psql -v ON_ERROR_STOP=1 -d "${DB_NAME}" <<SQL
GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};
GRANT ALL ON SCHEMA public TO ${DB_USER};
SQL

umask 077
if [[ ! -f "${ENV_FILE}" ]]; then
  SECRET_KEY="$(openssl rand -hex 32)"
  cat > "${ENV_FILE}" <<ENV
FLASK_CONFIG="production"
SECRET_KEY="${SECRET_KEY}"
DATABASE_URL="${DATABASE_URL}"
SITE_URL="https://www.${DOMAIN}"
MAIL_SERVER="smtp.gmail.com"
MAIL_PORT="587"
MAIL_USE_TLS="1"
MAIL_USE_SSL="0"
MAIL_USERNAME="${MAIL_USERNAME:-}"
MAIL_PASSWORD="${MAIL_PASSWORD:-}"
MAIL_DEFAULT_SENDER="Neural Xpert"
MAIL_DEFAULT_RECIPIENT="${MAIL_DEFAULT_RECIPIENT:-}"
CONTACT_RECIPIENT="${CONTACT_RECIPIENT:-${MAIL_DEFAULT_RECIPIENT:-}}"
UPLOAD_FOLDER="${APP_DIR}/instance/uploads"
ENV
  cat > "${CREDENTIALS_FILE}" <<CREDS
Neural Xpert production credentials
Database: PostgreSQL
Database name: ${DB_NAME}
Database user: ${DB_USER}
Database password: ${DB_PASSWORD}
Site: https://www.${DOMAIN}
CREDS
  chmod 600 "${CREDENTIALS_FILE}"
else
  env_set "${ENV_FILE}" FLASK_CONFIG production
  env_set "${ENV_FILE}" DATABASE_URL "${DATABASE_URL}"
  env_set "${ENV_FILE}" MAIL_DEFAULT_SENDER "Neural Xpert"
  if [[ -z "$(env_get "${ENV_FILE}" SITE_URL)" || "$(env_get "${ENV_FILE}" SITE_URL)" == "https://${DOMAIN}" ]]; then
    env_set "${ENV_FILE}" SITE_URL "https://www.${DOMAIN}"
  fi
  current_uploads="$(env_get "${ENV_FILE}" UPLOAD_FOLDER)"
  if [[ -z "${current_uploads}" || "${current_uploads}" == "instance/uploads" ]]; then
    env_set "${ENV_FILE}" UPLOAD_FOLDER "${APP_DIR}/instance/uploads"
  fi
  if [[ -n "${DB_PASSWORD:-}" ]]; then
    cat > "${CREDENTIALS_FILE}" <<CREDS
Neural Xpert production credentials
Database: PostgreSQL
Database name: ${DB_NAME}
Database user: ${DB_USER}
Database password: ${DB_PASSWORD}
Site: https://www.${DOMAIN}
CREDS
    chmod 600 "${CREDENTIALS_FILE}"
  fi
fi
chgrp www-data "${ENV_FILE}"
chmod 640 "${ENV_FILE}"
umask 022

if [[ ! -x "${APP_DIR}/.venv/bin/flask" ]]; then
  echo "Creating the application virtualenv..."
  python3 -m venv "${APP_DIR}/.venv"
fi
"${APP_DIR}/.venv/bin/pip" install --upgrade pip
"${APP_DIR}/.venv/bin/pip" install -r "${APP_DIR}/requirements.txt"
# www-data must be able to execute Gunicorn. The secrets file stays private.
chmod -R a+rX "${APP_DIR}/.venv"
find "${APP_DIR}" -path "${ENV_FILE}" -prune -o -type d -exec chmod a+rx {} +

load_env() {
  local line key value
  while IFS= read -r line || [[ -n "${line}" ]]; do
    line="${line%%$'\r'}"
    [[ -z "${line}" || "${line}" =~ ^[[:space:]]*# ]] && continue
    key="${line%%=*}"
    value="${line#*=}"
    if [[ "${value}" == \"*\" && "${value}" == *\" ]]; then
      value="${value:1:${#value}-2}"
    elif [[ "${value}" == \'*\' && "${value}" == *\' ]]; then
      value="${value:1:${#value}-2}"
    fi
    export "${key}=${value}"
  done < "$1"
}

if [[ ! -f "${APP_DIR}/migrations/env.py" ]]; then
  echo "migrations/ was not copied to ${APP_DIR}."
  exit 1
fi
if [[ ! -f "${APP_DIR}/app/visitors.py" || ! -f "${APP_DIR}/app/images.py" ]]; then
  echo "Visitor tracking or image uploads were not copied into ${APP_DIR}."
  exit 1
fi
if [[ ! -f "${APP_DIR}/migrations/versions/b7e2c4a91d08_page_visit_ips.py" ]] \
  || [[ ! -f "${APP_DIR}/migrations/versions/c8d4e1b72a05_content_image_size_radius.py" ]] \
  || [[ ! -f "${APP_DIR}/migrations/versions/d1a6f3c94e20_case_study_page_style.py" ]]; then
  echo "The visitor IP, image-size, or case-study style migration is missing. PostgreSQL would start without those columns."
  exit 1
fi

echo "Applying PostgreSQL migrations and seed data..."
(
  cd "${APP_DIR}"
  load_env .env
  case "${DATABASE_URL}" in
    postgresql*) ;;
    *)
      echo "DATABASE_URL must start with postgresql+psycopg://. MySQL is not used."
      exit 1
      ;;
  esac
  export FLASK_APP=wsgi:app
  export FLASK_CONFIG=production
  .venv/bin/flask db upgrade
  .venv/bin/flask seed
)

echo "Installing the Gunicorn service..."
cat > /etc/systemd/system/neuralxpert.service <<UNIT
[Unit]
Description=Neural Xpert Gunicorn
After=network.target postgresql.service

[Service]
User=www-data
Group=www-data
WorkingDirectory=${APP_DIR}
EnvironmentFile=${APP_DIR}/.env
Environment=FLASK_CONFIG=production
ExecStart=${APP_DIR}/.venv/bin/gunicorn --workers 3 --bind 127.0.0.1:8000 wsgi:app
Restart=on-failure

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable neuralxpert
systemctl restart neuralxpert

echo "Installing the Nginx site..."
CERT_DIR="/etc/letsencrypt/live/${DOMAIN}"
if [[ -f "${CERT_DIR}/fullchain.pem" && -f "${CERT_DIR}/privkey.pem" ]]; then
cat > /etc/nginx/sites-available/neuralxpert <<NGINX
server {
    listen 80;
    server_name ${DOMAIN} www.${DOMAIN};
    server_tokens off;
    client_max_body_size 6m;

    location ~ /\\.(?!well-known) {
        deny all;
    }

    location ^~ /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    location / {
        return 301 https://\$host\$request_uri;
    }
}

server {
    listen 443 ssl http2;
    server_name ${DOMAIN} www.${DOMAIN};
    server_tokens off;
    ssl_certificate ${CERT_DIR}/fullchain.pem;
    ssl_certificate_key ${CERT_DIR}/privkey.pem;
    client_max_body_size 6m;

    location ~ /\\.(?!well-known) {
        deny all;
    }

    location ^~ /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    location /static/uploads/ {
        alias ${APP_DIR}/app/static/uploads/;
        expires 7d;
        add_header Cache-Control "public" always;
        add_header X-Content-Type-Options nosniff always;
        add_header X-Frame-Options SAMEORIGIN always;
        add_header Referrer-Policy strict-origin-when-cross-origin always;
    }

    location /static/ {
        alias ${APP_DIR}/app/static/;
        expires 7d;
        add_header Cache-Control "public" always;
        add_header X-Content-Type-Options nosniff always;
        add_header X-Frame-Options SAMEORIGIN always;
        add_header Referrer-Policy strict-origin-when-cross-origin always;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$remote_addr;
        proxy_set_header X-Forwarded-Host \$host;
        proxy_set_header X-Forwarded-Proto https;
        proxy_redirect off;
    }
}
NGINX
else
cat > /etc/nginx/sites-available/neuralxpert <<NGINX
server {
    listen 80;
    server_name ${DOMAIN} www.${DOMAIN};
    server_tokens off;
    client_max_body_size 6m;

    location ~ /\\.(?!well-known) {
        deny all;
    }

    location ^~ /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    location /static/uploads/ {
        alias ${APP_DIR}/app/static/uploads/;
        expires 7d;
        add_header Cache-Control "public" always;
        add_header X-Content-Type-Options nosniff always;
        add_header X-Frame-Options SAMEORIGIN always;
        add_header Referrer-Policy strict-origin-when-cross-origin always;
    }

    location /static/ {
        alias ${APP_DIR}/app/static/;
        expires 7d;
        add_header Cache-Control "public" always;
        add_header X-Content-Type-Options nosniff always;
        add_header X-Frame-Options SAMEORIGIN always;
        add_header Referrer-Policy strict-origin-when-cross-origin always;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$remote_addr;
        proxy_set_header X-Forwarded-Host \$host;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_redirect off;
    }
}
NGINX
fi

ln -sfn /etc/nginx/sites-available/neuralxpert /etc/nginx/sites-enabled/neuralxpert
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl enable nginx
systemctl reload nginx

if [[ "${ENABLE_SSL:-1}" == "1" ]]; then
  echo "Requesting a TLS certificate for ${DOMAIN}..."
  apt-get install -y certbot python3-certbot-nginx
  if certbot --nginx \
    --non-interactive \
    --agree-tos \
    --redirect \
    -m "${CERTBOT_EMAIL}" \
    -d "${DOMAIN}" \
    -d "www.${DOMAIN}"; then
    systemctl reload nginx
  else
    echo "TLS was not issued. Point ${DOMAIN} and www.${DOMAIN} at this server, then run:"
    echo "  certbot --nginx -d ${DOMAIN} -d www.${DOMAIN}"
  fi
fi

sleep 2
if curl -fsS -o /dev/null "http://127.0.0.1:8000/"; then
  echo "Gunicorn is serving the site."
else
  echo "Gunicorn did not answer on port 8000. Check: journalctl -u neuralxpert -n 80 --no-pager"
  exit 1
fi

echo
echo "Uploaded images stay in ${APP_DIR}/app/static/uploads"
echo "Staff files and CVs stay in ${APP_DIR}/instance/uploads"
echo "Neural Xpert is installed at ${APP_DIR}"
echo "Public site: http://${DOMAIN}"
if [[ -f "${CREDENTIALS_FILE}" ]]; then
  echo "Database credentials are in ${CREDENTIALS_FILE}"
fi
echo "Service status: systemctl status neuralxpert --no-pager"
