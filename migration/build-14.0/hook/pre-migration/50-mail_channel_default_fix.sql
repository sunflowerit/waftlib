-- X-Modules: mail
UPDATE mail_channel SET group_public_id = NULL
WHERE channel_type <> 'channel' AND group_public_id = (
	SELECT res_id FROM ir_model_data WHERE module = 'base' AND name = 'group_user'
);
