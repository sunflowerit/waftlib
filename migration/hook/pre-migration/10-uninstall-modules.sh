#!/bin/bash
set -e

if [ ! -f "$MIGRATION_PATH/etc/uninstall-modules.txt" ]; then
	exit 0
fi
UNINSTALL_LIST=$(cat "$MIGRATION_PATH/etc/uninstall-modules.txt")


LAST_MODULE_NAME=""
for MODULE_NAME in ${UNINSTALL_LIST[@]} ""; do
    .venv/bin/python <<PYTHON
from anybox.recipe.odoo.runtime.session import Session


def test_uninstalled(module):
    """Check whether the given module is actually uninstalled.

    If its state is not "uninstalled" or "uninstallable", it is still in some sort of installed
    state.
    """
    if module.state not in ("uninstalled", "uninstallable"):
        raise Exception("Module %s was not uninstalled, has state \"%s\"" % (
            module.name,
            module.state
        ))


if "$MODULE_NAME".startswith("#"):
    exit(0)

session = Session("auto/odoo.conf", ".")
session.open()
env = session.env

# Check if the last module actually got uninstalled when exiting the shell.
print("$LAST_MODULE_NAME")
if "$LAST_MODULE_NAME":
    module = env["ir.module.module"].search([("name", "=", "$LAST_MODULE_NAME")])
    if module:
        test_uninstalled(module)

module = env["ir.module.module"].search([("name", "=", "$MODULE_NAME")])
if module and module.state not in ("uninstalled", "uninstallable"):
    print("Uninstalling $MODULE_NAME...")
    module.button_immediate_uninstall()

session.cr.commit()
session.close()
PYTHON

	LAST_MODULE_NAME="$MODULE_NAME"
done
