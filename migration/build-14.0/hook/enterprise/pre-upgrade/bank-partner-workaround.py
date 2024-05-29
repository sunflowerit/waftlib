# This workaround exists because the enterprise upgrade script doesn't
# handle res.partner.bank records very well that have no partner_id set.

if 'res.partner.bank' in env:
    without_partners = env['res.partner.bank'].search([('partner_id', '=', False)])

    if without_partners:
        dummy_partner = env['res.partner'].create({
            'name': 'Null Dummy Partner',
            'comment': "This partner is assigned to all res.partner.bank records that"
                    "have no partner set during the enterprise upgrade from 13.0 to"
                    "14.0." 
        })
        without_partners.partner_id = dummy_partner