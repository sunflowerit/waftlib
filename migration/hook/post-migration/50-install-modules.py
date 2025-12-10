# Install all the modules listed in
# etc/install-modules.txt
import logging
import traceback


try:
    file = open(MIGRATION_PATH + "/etc/install-modules.txt", "r")
except Exception as e:
    if type(e) == FileNotFoundError:
        logging.warning(
            "%s/etc/install-modules.txt doesn't exist, no modules will be installed.",
            MIGRATION_PATH,
        )
        raise SystemExit(0)
    if isinstance(e, IOError):
        logging.warning(
            "%s/etc/install-modules.txt can't be opened, no modules will be installed",
            MIGRATION_PATH,
        )
        traceback.print_exc()
        raise SystemExit(0)
    logging.error("Unable to open %s/etc/install-modules.txt:", MIGRATION_PATH)
    traceback.print_exc()
    raise SystemExit(1)

module_count = 0
for line in file:
    module_name = line.strip()
    if module_name:
        module_count += 1

logging.info("Installing %i modules..." % module_count)
file.seek(0)
for line in file:
    module_name = line.strip()
    if module_name and not module_name.startswith("#"):
        module = env["ir.module.module"].search([("name", "=", module_name)])
        if module and module.state != "installed":
            logging.info("Installing %s..." % module_name)
            module.button_immediate_install()
        else:
            logging.info("Module %s is already installed!" % module_name)
logging.info("Done installing modules.")
