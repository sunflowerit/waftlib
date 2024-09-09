-- X-Modules: mail
UPDATE mail_channel SET group_public_id = NULL WHERE channel_type <> 'channel';
DELETE FROM mail_channel_res_groups_rel WHERE mail_channel_id IN (
	SELECT id FROM mail_channel WHERE channel_type <> 'channel'
);
