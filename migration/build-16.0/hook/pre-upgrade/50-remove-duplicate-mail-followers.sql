-- X-Modules: mail

DELETE FROM mail_followers AS a USING mail_followers AS b
WHERE a.id < b.id
AND a.res_model = b.res_model
AND a.res_id = b.res_id
AND a.partner_id = b.partner_id;

DELETE FROM mail_notification AS a USING mail_notification AS b
WHERE a.id < b.id
AND a.mail_message_id = b.mail_message_id
AND a.res_partner_id = b.res_partner_id;
