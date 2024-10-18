from odoo.exceptions import UserError

cleanup_module = env["ir.module.module"].search([("name", "=", "database_cleanup")])

# Clean up the database using the database_cleanup module, temporarily install
# it if necessary.
if cleanup_module:
    was_installed = cleanup_module.state == "installed"
    if not was_installed:
        cleanup_module.button_immediate_install()
    try:
        wizard = env["cleanup.purge.wizard.module"].create({})
        wizard.purge_all()
    except UserError:
        pass
    if not was_installed:
        cleanup_module.button_immediate_uninstall()

# Update the module list
upd = env["base.module.update"].create({"state": "init"})
upd.update_module()
