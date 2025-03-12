#!/bin/bash
set -e

if [ ! -f "$MIGRATION_PATH/etc/uninstall-modules.txt" ]; then
   exit 0
fi
UNINSTALL_LIST=$(cat "$MIGRATION_PATH/etc/uninstall-modules.txt")


for MODULE_NAME in ${UNINSTALL_LIST[@]}; do
    .venv/bin/python <<PYTHON
from anybox.recipe.odoo.runtime.session import Session

if "$MODULE_NAME".startswith("#"):
    exit(0)

session = Session("auto/odoo.conf", ".")
session.open()
env = session.env

module = env["ir.module.module"].search([("name", "=", "$MODULE_NAME")])
if module and module.state != 'uninstalled':
    print("Uninstalling $MODULE_NAME...")
    module.button_immediate_uninstall()
    if module.state != 'uninstalled':
        raise Exception("Module %s was not uninstalled, has state \"%s\"" % (
            module.name,
            module.state
        ))

session.cr.commit()
session.close()
PYTHON
done
