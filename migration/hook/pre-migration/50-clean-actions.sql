DELETE FROM ir_actions WHERE "type" = 'ir.actions.report' AND id NOT IN (
    SELECT id FROM ir_act_report_xml
);
DELETE FROM ir_actions WHERE "type" = 'ir.actions.server' AND id NOT IN (
    SELECT id FROM ir_act_server
);
DELETE FROM ir_actions WHERE "type" = 'ir.actions.act_url' AND id NOT IN (
    SELECT id FROM ir_act_url
);
DELETE FROM ir_actions WHERE "type" = 'ir.actions.window' AND id NOT IN (
    SELECT id FROM ir_act_window
);
DELETE FROM ir_actions WHERE "type" = 'ir.actions.client' AND id NOT IN (
    SELECT id FROM ir_act_client
);
