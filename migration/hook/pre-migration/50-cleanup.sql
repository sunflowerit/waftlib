UPDATE res_users SET action_id = NULL WHERE action_id NOT IN (SELECT id FROM ir_actions);
