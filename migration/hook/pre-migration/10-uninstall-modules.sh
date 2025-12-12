#!/bin/bash
set -e

# Root of your Odoo build (adjust if needed)
SCRIPT_PATH="$(cd "$(/usr/bin/dirname "${0}")" && /bin/pwd)"
export MIGRATION_PATH="${MIGRATION_PATH:-$(cd "${SCRIPT_PATH}/../../migration" && /bin/pwd)}"

ODOO_CONF="${ODOO_CONF:-${MIGRATION_PATH}/build-${MIGRATION_START_VERSION}/auto/odoo.conf}"

if [[ ! -f "$MIGRATION_PATH/etc/uninstall-modules.txt" ]]; then
	exit 0
fi

source "${MIGRATION_PATH}/build-${MIGRATION_START_VERSION}/.venv/bin/activate"

click-odoo -c "$ODOO_CONF" <<'PYEOF'
import os
import sys
import logging
import traceback

logging.basicConfig(
    level=logging.INFO,
    stream=sys.stderr,
    format="%(message)s",
)

MIGRATION_PATH = os.environ.get("MIGRATION_PATH", os.getcwd())
uninstall_file = os.path.join(MIGRATION_PATH, "etc", "uninstall-modules.txt")

try:
    with open(uninstall_file, "r") as fff:
        module_names = [
            line.strip()
            for line in fff
            if line.strip() and not line.startswith("#")
        ]
except Exception as eee:
    logging.error("Failed to read uninstall file: %s", eee)
    sys.exit(1)

logging.info("Found %d modules to uninstall.", len(module_names))

module_model = env["ir.module.module"]

for module_name in module_names:
    logging.info("Processing module: %s", module_name)

    module = module_model.search([("name", "=", module_name)], limit=1)
    if not module:
        logging.info(" → Not found, skipping.")
        continue

    if module.state not in ("installed", "to install", "to upgrade"):
        logging.info(" → Already uninstalled (state=%s).", module.state)
        continue

    logging.info(" → Uninstalling...")
    try:
        module.button_immediate_uninstall()
        logging.info(" → Successfully uninstalled.")
    except Exception:
        logging.error(" → Failed uninstalling %s:", module_name)
        traceback.print_exc()
        # continue uninstalling the next modules instead of stopping

logging.info("All modules processed.")
PYEOF
