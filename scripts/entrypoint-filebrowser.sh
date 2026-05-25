#!/bin/sh
set -eu

DB_PATH="/database/filebrowser.db"
ROOT_PATH="/srv"

mkdir -p /database /config

if [ ! -f "${DB_PATH}" ]; then
  filebrowser config init -d "${DB_PATH}"
  filebrowser config set --database "${DB_PATH}" --root "${ROOT_PATH}"
  filebrowser config set --database "${DB_PATH}" --branding.name "${FILEBROWSER_PORTAL_NAME}"
  filebrowser users add "${FILEBROWSER_ADMIN_USER}" "${FILEBROWSER_ADMIN_PASSWORD}" --perm.admin --database "${DB_PATH}"
fi

exec filebrowser --database "${DB_PATH}" --root "${ROOT_PATH}" --port 80 --address 0.0.0.0
