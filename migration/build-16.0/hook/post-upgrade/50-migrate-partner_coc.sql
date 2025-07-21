-- X-Modules: partner_coc

WITH category AS (
	SELECT res_id AS id FROM ir_model_data
	WHERE module = 'partner_coc' AND name = 'id_category_coc'
	LIMIT 1
)
UPDATE res_partner rp SET company_registry = r.name
FROM (
	SELECT partner_id, name FROM res_partner_id_number
	WHERE category_id = (SELECT id FROM category)
) AS r
WHERE rp.id = r.partner_id;

-- TODO: Perform database cleanup of the partner_coc module
UPDATE ir_module_module SET state = 'uninstalled' WHERE name = 'partner_coc';
