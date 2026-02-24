-- Set the current timestamp + 30 days for database.expiration_date
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM ir_config_parameter WHERE key = 'database.expiration_date') THEN
    UPDATE ir_config_parameter
    SET value = (current_date + interval '30 days')::date::text
    WHERE key = 'database.expiration_date';
  ELSE
    INSERT INTO ir_config_parameter (key, value)
    VALUES ('database.expiration_date', (current_date + interval '30 days')::date::text);
  END IF;
END $$;

-- Set the current timestamp for database.create_date
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM ir_config_parameter WHERE key = 'database.create_date') THEN
    UPDATE ir_config_parameter
    SET value = current_date::text
    WHERE key = 'database.create_date';
  ELSE
    INSERT INTO ir_config_parameter (key, value)
    VALUES ('database.create_date', current_date::text);
  END IF;
END $$;

-- Echo out the updated values
SELECT key, value FROM ir_config_parameter WHERE key IN ('database.create_date', 'database.expiration_date');
