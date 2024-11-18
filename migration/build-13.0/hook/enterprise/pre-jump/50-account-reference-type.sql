-- This is a workaround for the account_payment_order module in Odoo 13.
-- Its migration script (wrongly) uses the reference_type column to copy
-- over its data. This field has been gone since Odoo 12.0, but it's
-- reintroduced in Odoo 13.0 in the account.move model. So it's a good
-- idea to keep the data on the side, so that it may be able to be
-- reinserted.
--
-- X-Supports-From: 9.0 10.0 11.0
-- X-Modules: account_payment_order
CREATE TABLE account_invoice_reference_type_backup (
    id INTEGER NOT NULL,
    reference_type VARCHAR NOT NULL
);
INSERT INTO account_invoice_reference_type_backup
SELECT id, reference_type FROM account_invoice;