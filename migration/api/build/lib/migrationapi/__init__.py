import psycopg2
import logging


class UnresolvableForeignReferenceError(Exception):
    def __init__(self, table_name, column_name, column_value):
        self.table_name = table_name
        self.column_name = column_name
        self.column_value = column_value


DESTRUCTION_TABLE_WHITELIST = [
    "ir_cron",
    "ir_model_fields",
    "ir_ui_view",
    "ir_ui_view_custom",
    "ir_ui_view_group_rel",
]


def delete_table_references(env, table_name, column_name, id, careful=True):
    """ Removes all references to a specific record of a table in the
        database. However, because this can be quite destructive, this
        function uses a whitelist of database tables that it is allowed
        to delete from. Otherwise you might end up deleting things like
        sale orders just because you want a view gone. Unless careful is
        set to False.
    """
    env.cr.execute("""
        SELECT r.table_name, r.column_name, rc.is_nullable FROM information_schema.constraint_column_usage AS u
        INNER JOIN information_schema.columns AS c
            ON u.constraint_catalog = c.table_catalog
                AND u.constraint_schema = c.table_schema
                AND u.table_name = c.table_name
                AND u.column_name = c.column_name
        INNER JOIN information_schema.referential_constraints AS fk
            ON u.constraint_catalog = fk.unique_constraint_catalog
                AND u.constraint_schema = fk.unique_constraint_schema
                AND u.constraint_name = fk.unique_constraint_name
        INNER JOIN information_schema.key_column_usage AS r
            ON r.constraint_catalog = fk.constraint_catalog
                AND r.constraint_schema = fk.constraint_schema
                AND r.constraint_name = fk.constraint_name
        INNER JOIN information_schema.columns AS rc
            ON rc.table_catalog = c.table_catalog
                AND rc.table_name = r.table_name
                AND rc.column_name = r.column_name
        WHERE
            u.column_name = %s AND
            u.table_name = %s
    """, [column_name, table_name])
    result = env.cr.dictfetchall()
    for reference in result:
        env.cr.execute("SELECT COUNT(*) FROM "+reference['table_name']+" WHERE "+reference['column_name']+" = %s", [id])
        num_refs = env.cr.fetchone()[0]
        if num_refs > 0:
            if reference['is_nullable'] == 'YES':
                logging.info("Setting %s to NULL on %s.", reference['column_name'], reference['table_name'])
                env.cr.execute("UPDATE "+reference['table_name']+" SET "+reference['column_name']+" = NULL WHERE "+reference['column_name']+" = %s", [id])
            else:
                logging.info("Deleting records on %s with %s set to %i", reference['table_name'], reference['column_name'], id)
                delete_record_by_column(env, reference['table_name'], reference['column_name'], id, careful)


def delete_record_by_column(env, table_name, column_name, column_value, careful):
    if careful and not table_name in DESTRUCTION_TABLE_WHITELIST:
        raise UnresolvableForeignReferenceError(table_name, column_name, column_value)

    env.cr.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = %s AND column_name = 'id'",
        [table_name]
    )
    # If the table has an 'id' column, delete foreign references to this
    # first.
    if env.cr.dictfetchone():
        env.cr.execute("SELECT id FROM "+table_name+" WHERE "+column_name+" = %s", [column_value])
        ids = env.cr.dictfetchall()
        for row in ids:
            delete_table_references(env, table_name, 'id', row['id'], careful)
    env.cr.execute("DELETE FROM "+table_name+" WHERE "+column_name+" = %s", [column_value])


def purge_model(env, model_id, careful=True):
    def unlink_model():
        env.cr.rollback()
        # Always works, but is VERY slow:
        delete_table_references(env, 'ir_model', 'id', model_id, careful)
        env.cr.execute("DELETE FROM ir_model WHERE id = %s",
                [model_id])

    env.cr.execute("SELECT name FROM ir_model WHERE id = %s", [model_id])
    model_name = env.cr.fetchone()[0]
    env.cr.commit()
    try:
        env.cr.execute("DELETE FROM ir_cron WHERE ir_actions_server_id IN ("
            "SELECT id FROM ir_act_server WHERE model_id = %s"
        ")", [model_id])
        env.cr.execute("DELETE FROM ir_act_server WHERE model_id = %s", [model_id])
        env.cr.execute("DELETE FROM ir_model_access WHERE model_id = %s", [model_id])
        env.cr.execute("DELETE FROM ir_model_constraint WHERE model = %s", [model_id])
        env.cr.execute("DELETE FROM ir_model_fields WHERE model_id = %s OR relation_table = %s", [model_id, model_name])
        env.cr.execute("DELETE FROM ir_model_relation WHERE model = %s", [model_id])
        env.cr.execute("DELETE FROM ir_rule WHERE model_id = %s", [model_id])
        env.cr.execute("DELETE FROM ir_model WHERE id = %s", [model_id])
    except psycopg2.errors.ForeignKeyViolation:
        unlink_model()
    except psycopg2.errors.NotNullViolation:
        unlink_model()


def purge_view(env, view_id):
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
        purge_view(env, child['id'])

    logging.info("Deleting view %i..." % view_id)
    env.cr.execute("DELETE FROM ir_ui_view_group_rel WHERE view_id = %s", [view_id])
    try:
        env.cr.execute("DELETE FROM ir_ui_view WHERE id = %s", [view_id])
    except psycopg2.errors.ForeignKeyViolation:
        unlink_view()
    except psycopg2.errors.NotNullViolation:
        unlink_view()
    env.cr.execute("DELETE FROM ir_model_data WHERE model = 'ir.ui.view' AND res_id = %s", [view_id])
    env.cr.commit()
    return True

