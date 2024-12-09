# Uninstall all the modules listed in
# etc/uninstall-modules.txt
import os
import sys
import traceback


try:
    file = open(MIGRATION_PATH + "/etc/uninstall-modules.txt", "r")
except Exception as e:
    if type(e) == "FileNotFoundError":
        logging.warning(
            "%s/etc/uninstall-modules.txt doesn't exist, no modules will be uninstalled.",
            MIGRATION_PATH,
        )
        exit(0)
    if isinstance(e, IOError):
        logging.warning(
            "%s/etc/uninstall-modules.txt can't be opened, no modules will be uninstalled",
            MIGRATION_PATH,
        )
        traceback.print_exc()
        exit(0)
    # else:
    logging.error("Unable to open %s/etc/uninstall-modules.txt:", MIGRATION_PATH)
    traceback.print_exc()
    exit(1)

module_names = []
for line in file:
    module_name = line.strip()
    if module_name:
        module_names.append(module_name)

logging.info(
    "Uninstalling %i modules..." % len(module_names),
)

for module in env["ir.module.module"].search([("name", "in", module_names)]):
    if not module.state in ('uninstalled', 'to remove'):
        module.button_immediate_uninstall()
        env.cr.commit()
