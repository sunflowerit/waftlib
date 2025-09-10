-- X-Modules: mail

UPDATE mail_mail SET scheduled_date = NULL WHERE TRIM(scheduled_date) = '';
