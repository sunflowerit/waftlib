# X-Modules: account

import logging


lines = env["account.bank.statement.line"].search([("currency_id", "=", False)])
if lines:
    if len(lines) < 10:
        for line in lines:
            logging.error("Bank statement line %s has no currency_id set." % line.id)
    raise Exception("One or more bank statement lines do not have a currency_id set.")
