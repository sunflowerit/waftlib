-- X-Supports-From: 9.0 10.0 11.0 12.0
ALTER TABLE account_move ADD COLUMN old_invoice_id INTEGER;
UPDATE account_move am SET old_invoice_id = ai.id
FROM account_invoice ai WHERE ai.move_id = am.id;
