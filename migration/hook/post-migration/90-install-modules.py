# Install all the modules listed in
# etc/post-migration-install-modules.txt
import os
import sys


try:
    file = open(MIGRATION_PATH + '/etc/install-modules.txt', 'r')
except FileNotFoundError:
    exit(0)

module_count = 0
for line in file:
    module_name = line.strip()
    if module_name:
        module_count += 1

logging.info("Installing %i modules..." % module_count)
file.seek(0)
for line in file:
    module_name = line.strip()
    if module_name and not module_name.startswith('#'):
        module = env['ir.module.module'].search([('name', '=', module_name)])
        if module and module.state != 'installed':
            logging.info("Installing %s..." % module_name)
            module.button_immediate_install()
        else:
            logging.info("Module %s is already installed!" % module_name)
logging.info("Done installing modules.")
