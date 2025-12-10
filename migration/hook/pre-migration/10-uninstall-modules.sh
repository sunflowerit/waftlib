#!/bin/bash
set -e

# Root of your Odoo build (adjust if needed)
SCRIPT_PATH="$(cd "$(/usr/bin/dirname "${0}")" && /bin/pwd)"
export MIGRATION_PATH="${MIGRATION_PATH:-$(cd "${SCRIPT_PATH}/../../migration" && /bin/pwd)}"

ODOO_CONF="${ODOO_CONF:-$BUILD_DIR/auto/odoo.conf}"

if [[ ! -f "$MIGRATION_PATH/etc/uninstall-modules.txt" ]]; then
	exit 0
fi

source "${$MIGRATION_PATH}/build-${MIGRATION_START_VERSION}/.venv/bin/activate"

click-odoo -c "$ODOO_CONF" shell <<'PYEOF'
import os
import sys
import logging
import traceback

MIGRATION_PATH = os.environ.get("MIGRATION_PATH", os.getcwd())
uninstall_file = os.path.join(MIGRATION_PATH, "etc", "uninstall-modules.txt")

logging.basicConfig(
    level=logging.INFO,
    stream=sys.stderr,
    format="%(message)s",
)

try:
    f = open(uninstall_file, "r")
except FileNotFoundError:
    logging.warning("%s doesn't exist, no modules will be uninstalled.", uninstall_file)
    sys.exit(0)
except IOError:
    logging.warning("%s can't be opened, no modules will be uninstalled.", uninstall_file)
    traceback.print_exc()
    sys.exit(0)
except Exception:
    logging.error("Unable to open %s:", uninstall_file)
    traceback.print_exc()
    sys.exit(1)

module_names = []
for line in f:
    name = line.strip()
    if name and not name.startswith("#"):
        module_names.append(name)

logging.info("Uninstalling %d modules...", len(module_names))

model = env["ir.module.module"]

for module_name in module_names:
    mods = model.search([("name", "=", module_name)])
    if not mods:
        logging.info("Module %s not found, skipping.", module_name)
        continue

    for mod in mods:
        if mod.state in ("installed", "to install", "to upgrade"):
            logging.info("Uninstalling %s...", module_name)
            mod.button_immediate_uninstall()
        else:
            logging.info("Module %s already uninstalled (state=%s).", module_name, mod.state)

logging.info("Done uninstalling modules.")
PYEOF
