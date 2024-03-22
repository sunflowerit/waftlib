# In Odoo 12, the certificate field is added to hr.employee. However, in
# this version, it has the default value set to "Master". So this script
# resets it to being empty, which is more meaningful.
#
# X-Modules: hr


if 'hr.employee' in env:
    employees = env['hr.employee'].search([])
    for employee in employees:
        employee.certificate = False