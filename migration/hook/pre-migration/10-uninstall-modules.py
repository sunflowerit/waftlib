# Uninstall all the modules listed in
# etc/uninstall-modules.txt
import os
import sys


try:
    file = open(MIGRATION_PATH + "/etc/uninstall-modules.txt", "r")
except FileNotFoundError:
    logging.info("%s/etc/uninstall-modules.txt doesn't exist, no modules will be uninstalled.", MIGRATION_PATH)
    exit(0)

module_names = []
for line in file:
    module_name = line.strip()
    if module_name:
        module_names.append(module_name)

logging.info(
    "Uninstalling %i modules..." % len(module_names),
)

for module in env["ir.module.module"].search([("name", "in", module_names)]):
    module.state = 'to remove'
env.cr.commit()
