# This script will purge all lines from any BoM that at some point uses
# itself (a parent product) as a material. This is impossible and should
# have been done in the first place, but the enterprise upgrade script
# takes issue with this during the 13.0 upgrade.
#
# X-Supports-From: 10.0
# X-Modules: product
import copy


def _purge_template_boms(template, _path):
    products = [ product.id for product in template.product_variant_ids]

    for bom in template.bom_ids:
        path = copy.deepcopy(_path)
        path.append((template.id, products, bom.id))
        _purge_template_bom_lines(bom, path)

def _purge_template_bom_lines(bom, path):
    for line in bom.bom_line_ids:
        # Disconnect the BoM from the parent product template that has
        # the same product.
        for element in path:
            if line.product_id.id in element[1]:
                logging.info("Removing line %i from BoM %i, for product template %i." % 
                    (line.id, bom.id, element[0]))
                bom.bom_line_ids = [(3, line.id, None)]
                break

    # Recurse into product templates of BoM lines.
    for line in bom.bom_line_ids:
        template = line.product_id.product_tmpl_id
        _purge_template_boms(template, path)

def purge_template_materials(product_template):
    _purge_template_boms(product_template, [])


templates = env['product.template'].search([])

logging.info("Purging recursive bill of materials...")
for template in templates:
    purge_template_materials(template)
