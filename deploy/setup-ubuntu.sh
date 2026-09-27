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
#   DOMAIN=neuralxpert.com ADMIN_EMAIL=admin@neuralxpert.com bash deploy/setup-ubuntu.sh

set -euo pipefail

APP_DIR="${APP_DIR:-/var/www/neuralxpert}"
DOMAIN="${DOMAIN:-neuralxpert.com}"
DB_NAME="${DB_NAME:-neuralxpert}"
DB_USER="${DB_USER:-neuralxpert}"
ADMIN_EMAIL="${ADMIN_EMAIL:-admin@neuralxpert.com}"
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
  "${SOURCE_DIR}/" "${APP_DIR}/"

install -d -o www-data -g www-data -m 750 "${APP_DIR}/instance"
install -d -o www-data -g www-data -m 750 "${APP_DIR}/instance/uploads"

if [[ ! -f "${APP_DIR}/.env" ]]; then
  echo "Creating PostgreSQL role and database..."
  DB_PASSWORD="$(openssl rand -hex 24)"
  SECRET_KEY="$(openssl rand -hex 32)"
  ADMIN_PASSWORD="$(openssl rand -base64 24 | tr -d '/+=' | head -c 24)"

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

  if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname = '${DB_NAME}'" | grep -q 1; then
    sudo -u postgres createdb --owner="${DB_USER}" "${DB_NAME}"
  fi
  sudo -u postgres psql -v ON_ERROR_STOP=1 -d "${DB_NAME}" <<SQL
GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};
GRANT ALL ON SCHEMA public TO ${DB_USER};
SQL

  umask 077
  cat > "${APP_DIR}/.env" <<ENV
FLASK_CONFIG=production
SECRET_KEY=${SECRET_KEY}
DATABASE_URL=postgresql+psycopg://${DB_USER}:${DB_PASSWORD}@localhost:5432/${DB_NAME}
SITE_URL=https://${DOMAIN}
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=1
MAIL_USE_SSL=0
MAIL_USERNAME=
MAIL_PASSWORD=
MAIL_DEFAULT_SENDER=Neural Xpert
MAIL_DEFAULT_RECIPIENT=
CONTACT_RECIPIENT=
ADMIN_EMAIL=${ADMIN_EMAIL}
ADMIN_PASSWORD=${ADMIN_PASSWORD}
ENV
  cat > "${CREDENTIALS_FILE}" <<CREDS
Neural Xpert production credentials
Database: ${DB_NAME}
Database user: ${DB_USER}
Database password: ${DB_PASSWORD}
Admin email: ${ADMIN_EMAIL}
Admin password: ${ADMIN_PASSWORD}
Site: https://${DOMAIN}
CREDS
  chmod 600 "${APP_DIR}/.env" "${CREDENTIALS_FILE}"
  chgrp www-data "${APP_DIR}/.env"
  chmod 640 "${APP_DIR}/.env"
else
  echo "Keeping the existing ${APP_DIR}/.env"
fi

if [[ ! -x "${APP_DIR}/.venv/bin/flask" ]]; then
  echo "Creating the application virtualenv..."
  python3 -m venv "${APP_DIR}/.venv"
fi
"${APP_DIR}/.venv/bin/pip" install --upgrade pip
"${APP_DIR}/.venv/bin/pip" install -r "${APP_DIR}/requirements.txt"

echo "Applying database migrations and seed data..."
(
  cd "${APP_DIR}"
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
  export FLASK_APP=wsgi:app
  .venv/bin/flask db upgrade
  .venv/bin/flask seed
  if [[ -n "${ADMIN_PASSWORD:-}" ]]; then
    .venv/bin/flask create-admin
  fi
)

# The running web process does not need the admin password.
if grep -q '^ADMIN_PASSWORD=' "${APP_DIR}/.env"; then
  grep -v '^ADMIN_PASSWORD=' "${APP_DIR}/.env" > "${APP_DIR}/.env.tmp"
  mv "${APP_DIR}/.env.tmp" "${APP_DIR}/.env"
  chgrp www-data "${APP_DIR}/.env"
  chmod 640 "${APP_DIR}/.env"
fi

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
cat > /etc/nginx/sites-available/neuralxpert <<NGINX
server {
    listen 80;
    server_name ${DOMAIN} www.${DOMAIN};
    server_tokens off;
    client_max_body_size 8m;

    location ^~ /.well-known/acme-challenge/ {
        root /var/www/html;
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
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_redirect off;
    }
}
NGINX

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
echo "Neural Xpert is installed at ${APP_DIR}"
echo "Public site: http://${DOMAIN}"
if [[ -f "${CREDENTIALS_FILE}" ]]; then
  echo "Database and admin passwords are in ${CREDENTIALS_FILE}"
fi
echo "Service status: systemctl status neuralxpert --no-pager"
