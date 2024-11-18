-- See pre-jump/50-account-reference-type.sql for more info.
--
-- X-Supports: 13.0
-- X-Supports-From: 9.0 10.0 11.0
-- X-Modules: account_payment_order

ALTER TABLE account_invoice ADD COLUMN IF NOT EXISTS reference_type VARCHAR;
UPDATE account_invoice ai SET reference_type = backup.reference_type
FROM account_invoice_reference_type_backup AS backup
WHERE backup.id = ai.id;
DROP TABLE account_invoice_reference_type_backup;