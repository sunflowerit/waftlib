# Uninstall all the modules listed in etc/uninstall-modules.txt that aren't
# uninstalled yet by the script that uses `button_immediate_uninstall`.
import traceback


try:
    file = open(MIGRATION_PATH + "/etc/uninstall-modules.txt", "r")
except Exception as e:
    # else:
    logging.error("Unable to open %s/etc/uninstall-modules.txt:", MIGRATION_PATH)
    traceback.print_exc()
    exit(1)

module_names = []
for line in file:
    module_name = line.strip()
    if module_name:
        module_names.append(module_name)


for module in env["ir.module.module"].search([("name", "in", module_names)]):
    if not module.state in ('uninstalled', 'to remove'):
        env.cr.execute("""
            UPDATE ir_module_module SET state = 'to remove' WHERE id = %s
        """, [module.id])
env.cr.commit()
