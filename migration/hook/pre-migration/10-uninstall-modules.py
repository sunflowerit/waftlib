# Uninstall all the modules listed in
# etc/uninstall-modules.txt
import os
import sys


try:
    file = open(MIGRATION_PATH + "/etc/uninstall-modules.txt", "r")
except FileNotFoundError:
    exit(0)

module_count = 0
for line in file:
    module_name = line.strip()
    if module_name:
        module_count += 1

logging.info(
    "Uninstalling %i modules..." % module_count,
)

module_succeeded = True
module_failed = False
while module_succeeded:
    module_succeeded = False
    module_failed = False
    file.seek(0)
    for line in file:
        module_name = line.strip()
        if module_name and not module_name.startswith("#"):
            module = env["ir.module.module"].search([("name", "=", module_name)])
            if module and module.state in ("installed", "to upgrade", "to remove"):
                logging.info("Uninstalling %s..." % module_name)
                module.button_immediate_uninstall()
                env.cr.commit()
                if module.state in ("installed", "to upgrade", "to remove"):
                    module_failed = True
                    logging.warn("Failed to remove module %s this time." % module_name)
                else:
                    module_succeeded = True
                    logging.info("Uninstalled %s." % module_name)
            else:
                logging.info(
                    "Module %s is not installed! (%s)" % (module_name, module.state)
                )

logging.info("Done uninstalling modules.")
if module_failed:
    logging.error("Some module(s) still failed to uninstall.")
    exit(1)
