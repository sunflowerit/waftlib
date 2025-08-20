# X-Modules: partner_coc

env["ir.module.module"].search(
    [("name", "=", "partner_coc")]
).button_immediate_uninstall()
