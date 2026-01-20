#!/bin/bash
set -Eeuo pipefail

SCRIPT_PATH="$(cd "$(/usr/bin/dirname "${0}")" && /bin/pwd)"
export MIGRATION_PATH="${MIGRATION_PATH:-$(cd "${SCRIPT_PATH}/../../../../migration" && /bin/pwd)}"

: "${MIGRATION_START_VERSION:?MIGRATION_START_VERSION must be set (e.g. 14.0)}"
ODOO_CONF="${ODOO_CONF:-${MIGRATION_PATH}/build-${MIGRATION_START_VERSION}/auto/odoo.conf}"

UNINSTALL_FILE="${MIGRATION_PATH}/etc/uninstall-modules.txt"
VENV_ACTIVATE="${MIGRATION_PATH}/build-${MIGRATION_START_VERSION}/.venv/bin/activate"

if [[ ! -f "${UNINSTALL_FILE}" ]]; then
  exit 0
fi

if [[ ! -f "${VENV_ACTIVATE}" ]]; then
  echo "ERROR: venv activate script not found: ${VENV_ACTIVATE}" >&2
  exit 1
fi

source "${VENV_ACTIVATE}"

# Parse module list (ignore blanks and comment lines that start with '#', optionally preceded by spaces)
mapfile -t MODULES < <(
  sed -e 's/[[:space:]]\+$//' \
      -e '/^[[:space:]]*$/d' \
      -e '/^[[:space:]]*#/d' \
      "${UNINSTALL_FILE}"
)

if (( ${#MODULES[@]} == 0 )); then
  exit 0
fi

echo "Found ${#MODULES[@]} modules to uninstall."

FAILED=0

for module_name in "${MODULES[@]}"; do
  echo "Processing module: ${module_name}"

  # Run click-odoo once per module
  if ! click-odoo -c "${ODOO_CONF}" <<PYEOF
import logging
import sys
import traceback

logging.basicConfig(level=logging.INFO, stream=sys.stderr, format="%(message)s")

module_name = ${module_name@Q}

module_model = env["ir.module.module"]
module = module_model.search([("name", "=", module_name)], limit=1)

if not module:
    logging.info(" → Not found, skipping.")
    raise SystemExit(0)

if module.state not in ("installed", "to install", "to upgrade"):
    logging.info(" → Already uninstalled (state=%s).", module.state)
    raise SystemExit(0)

logging.info(" → Uninstalling...")
try:
    module.button_immediate_uninstall()
    logging.info(" → Successfully uninstalled.")
except Exception:
    logging.error(" → Failed uninstalling %s:", module_name)
    traceback.print_exc()
    raise SystemExit(2)
PYEOF
  then
    echo "ERROR: uninstall failed for ${module_name}" >&2
    FAILED=1
    # continue with next module
  fi
done

if (( FAILED != 0 )); then
  echo "Completed with failures." >&2
  exit 1
fi

echo "All modules processed successfully."

