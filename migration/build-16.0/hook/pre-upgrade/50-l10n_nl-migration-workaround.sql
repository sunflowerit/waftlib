-- X-Modules: l10n_nl
--
-- This query prevents an error in one of the migration scripts of the l10n_nl
-- module.
-- An empty value for web.base.url can cause en error.

UPDATE ir_config_parameter SET "value" = 'empty'
WHERE "key" = 'web.base.url' AND "value" in ('', NULL);
