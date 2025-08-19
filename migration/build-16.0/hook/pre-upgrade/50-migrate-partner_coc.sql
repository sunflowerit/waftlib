-- X-Modules: partner_coc

ALTER TABLE res_partner ADD COLUMN company_registry VARCHAR;

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

-- Have the partner_coc module uninstalled
UPDATE ir_module_module SET state = 'to remove' WHERE name = 'partner_coc';
