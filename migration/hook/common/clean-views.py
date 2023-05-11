# Cleans invalid/problematic view records.
from migrationapi import delete_table_references, UnresolvableForeignReferenceError

try:
    from odoo.addons.base.models.ir_ui_view import get_view_arch_from_file
except ImportError:
    from odoo.addons.base.ir.ir_ui_view import get_view_arch_from_file
from odoo.exceptions import MissingError, ValidationError
from odoo.modules.module import get_resource_path

try:
    import psycopg
except ImportError:
    import psycopg2 as psycopg


def delete_view(view_id):
    def unlink_view():
        env.cr.rollback()
        try:
            delete_table_references(env, 'ir_ui_view', 'id', view_id)
        except UnresolvableForeignReferenceError as e:
            logging.info("Warning: unable to delete view %i: there is a foreign "
                  "reference with table %s (column %s = %s), which can't just "
                  "be deleted. Skipping this view for now..." % (
                    view_id,
                    e.table_name,
                    e.column_name,
                    str(e.column_value)
                  )
            )
            return False
        env.cr.execute("DELETE FROM ir_ui_view WHERE id = %s", [view_id])

    env.cr.execute("SELECT id FROM ir_ui_view WHERE inherit_id = %s", [view_id])
    result = env.cr.dictfetchall()
    for child in result:
        delete_view(child['id'])

    logging.info("Deleting view %i..." % view_id)
    env.cr.execute("DELETE FROM ir_ui_view_group_rel WHERE view_id = %s", [view_id])
    try:
        env.cr.execute("DELETE FROM ir_ui_view WHERE id = %s", [view_id])
    except psycopg.errors.ForeignKeyViolation:
        unlink_view()
    except psycopg.errors.NotNullViolation:
        unlink_view()
    env.cr.execute("DELETE FROM ir_model_data WHERE model = 'ir.ui.view' AND res_id = %s", [view_id])
    env.cr.commit()
    return True


def purge_views():
    env.cr.execute("SELECT id FROM ir_ui_view")
    result = env.cr.dictfetchall()
    for row in result:
        try:
            view = env['ir.ui.view'].browse(row['id'])
            view.arch_fs
        except MissingError:
            continue

        if view.arch_fs:
            missing = False
            fullpath = get_resource_path(*view.arch_fs.split('/'))
            if fullpath:
                if view.xml_id:
                    try:
                        arch = get_view_arch_from_file(fullpath, view.xml_id)
                        if arch == None:
                            missing = True
                        else:
                            try:
                                view._check_xml()
                            except ValueError:
                                delete_view(view.id)
                    except ValidationError:
                        delete_view(view.id)
            else:
                missing = True
            if missing:
                delete_view(view.id)


purge_views()
logging.info("Cleaned views.")
