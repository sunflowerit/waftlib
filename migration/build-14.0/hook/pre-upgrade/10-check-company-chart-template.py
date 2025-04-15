# X-Modules: account

import logging


companies = env["res.company"].search([("chart_template_id", "=", False)])
if companies:
    for company in companies:
        logging.error("Company %s has no chart_template_id set." % company.name)
    raise Exception("One or more companies do no have chart_template_id set.")