-- X-Modules: mail

DELETE FROM mail_notification AS a USING mail_notification AS b
WHERE a.id < b.id
AND a.mail_message_id = b.mail_message_id
AND a.res_partner_id = b.res_partner_id;
