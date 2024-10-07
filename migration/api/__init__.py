import psycopg2
import logging


class UnresolvableForeignReferenceError(Exception):
    def __init__(self, table_name, column_name, column_value):
        self.table_name = table_name
        self.column_name = column_name
        self.column_value = column_value


DESTRUCTION_TABLE_WHITELIST = [
    "ir_act_client",
    "ir_act_report_xml",
    "ir_act_server",
    "ir_act_server_group_rel",
    "ir_act_server_res_partner_rel",
    "ir_act_url",
    "ir_act_window",
    "ir_act_window_group_rel",
    "ir_act_window_view",
    "ir_actions",
    "ir_cron",
    "ir_model_fields",
    "ir_model_fields_selection",
    "ir_ui_view",
    "ir_ui_view_custom",
    "ir_ui_view_group_rel",
]


def fetch_foreign_key_constraints(cr, table_name):
    cr.execute(
        """
        SELECT r.table_name, r.constraint_name, r.column_name, rc.is_nullable FROM information_schema.constraint_column_usage AS u
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
                u.column_name = 'id' AND
                u.table_name = %s
    """,
        [table_name],
    )
    results = cr.dictfetchall()
    return [
        (
            r["constraint_name"],
            r["table_name"],
            r["column_name"],
            r["is_nullable"] == "YES",
        )
        for r in results
    ]


tables_already_cleaned = []


def clean_foreign_references(cr, table_name, constraints, reset_id, filter=None):
    global tables_already_cleaned
    for constraint, foreign_table_name, foreign_column, is_nullable in constraints:
        delete = False
        update_value = None
        if is_nullable:
            logging.info(
                "Resetting foreign references to null from %s.%s to %s."
                % (foreign_table_name, foreign_column, table_name)
            )
        else:
            logging.info("X", reset_id)
            update_value = reset_id
            if not reset_id:
                delete = True
                logging.info(
                    "Deleting foreign references from %s.%s to %s."
                    % (foreign_table_name, foreign_column, table_name)
                )
            else:
                logging.info(
                    "Resetting foreign references to %s from %s.%s to %s."
                    % (update_value, foreign_table_name, foreign_column, table_name)
                )

        if not filter:
            filter_template = 'NOT IN (SELECT id FROM "%s")'
        else:
            filter_template = '< (SELECT %s(id) FROM "%s")' % (filter, "%s")
        filter_clause = filter_template % table_name
        if not delete:
            cr.execute(
                'CREATE INDEX "%s_temp_index" ON "%s" ("%s")'
                % (constraint, foreign_table_name, foreign_column)
            )
            query = """
                UPDATE \"%s\" SET \"%s\" = %s WHERE \"%s\" %s
            """ % (
                foreign_table_name,
                foreign_column,
                "%s",
                foreign_column,
                filter_clause,
            )
            logging.info(query, update_value)
            cr.execute(
                query,
                [update_value],
            )
            cr.execute('DROP INDEX "%s_temp_index"' % constraint)
        else:
            if not foreign_table_name in tables_already_cleaned:
                tables_already_cleaned.append(foreign_table_name)
                cr.execute(
                    'CREATE INDEX "%s_temp_index" ON "%s" ("%s")'
                    % (constraint, foreign_table_name, foreign_column)
                )
                purge_records_more_than_reserve(
                    cr, foreign_table_name, '"%s" %s' % (foreign_column, filter_clause)
                )
                cr.execute('DROP INDEX "%s_temp_index"' % constraint)


def purge_records(cr, table_name, where_clause, reset_id, non_updatable_tables=[]):
    constraints = fetch_foreign_key_constraints(cr, table_name)
    _disable_constraints(cr, table_name, constraints)

    query = """  
                CREATE TABLE yyy AS (WITH xxx AS (DELETE FROM \"%s\" WHERE %s RETURNING ID) SELECT id FROM xxx)
        """ % (
        table_name,
        where_clause,
    )
    logging.info(query)
    cr.execute(query)

    for _, foreign_table_name, foreign_column, is_nullable in constraints:
        if reset_id and (
            not foreign_table_name.endswith("_rel")
            and foreign_table_name not in non_updatable_tables
        ):
            update_value = "NULL" if is_nullable else reset_id
            query = """
				UPDATE \"%s\" SET \"%s\" = %s WHERE \"%s\" IS NOT NULL AND \"%s\" IN (SELECT id FROM yyy)
                        """ % (
                foreign_table_name,
                foreign_column,
                update_value,
                foreign_column,
                foreign_column,
            )
        else:
            query = """
				DELETE FROM \"%s\" WHERE \"%s\" IN (SELECT id FROM yyy)
			""" % (
                foreign_table_name,
                foreign_column,
            )
        logging.info(query)
        cr.execute(query)
    logging.info("DROP TABLE yyy")
    cr.execute("DROP TABLE yyy")


def purge_records_more_than_reserve(
    cr, table_name, where_clause, reset_id=None, filter=None
):
    _execute_without_constraints(
        cr,
        table_name,
        reset_id,
        'DELETE FROM "%s" WHERE %s' % (table_name, where_clause),
        filter,
    )


def _disable_constraints(cr, table_name, constraints):
    query = 'ALTER TABLE "%s" DISABLE TRIGGER ALL' % table_name
    logging.info(query)
    cr.execute(query)


def _enable_constraints(cr, table_name, constraints):
    for constraint_name, foreign_table_name, foreign_column, _ in constraints:
        query = "UPDATE pg_constraint SET convalidated = FALSE WHERE conname = %s"
        logging.info(query, constraint_name)
        cr.execute(query, [constraint_name])
        query = 'ALTER TABLE "%s" VALIDATE CONSTRAINT "%s"' % (
            foreign_table_name,
            constraint_name,
        )
        logging.info(query, constraint_name)
        cr.execute(query, [constraint_name])


def _execute_without_constraints(cr, table_name, reset_id, query, filter):
    logging.info("Reading constraints from %s." % table_name)
    constraints = fetch_foreign_key_constraints(table_name)
    if constraints:
        logging.info("Disabling foreign references to %s." % table_name)
        _disable_constraints(table_name, constraints)
    logging.info(query)
    cr.execute(query)
    if constraints:
        logging.info("Cleaning old foreign references of %s" % table_name)
        clean_foreign_references(table_name, constraints, reset_id, filter)
        logging.info("Enabling foreign references to %s." % table_name)
        _enable_constraints(table_name, constraints)


def delete_table_references(env, table_name, column_name, id, careful=True):
    """Removes all references to a specific record of a table in the
    database. However, because this can be quite destructive, this
    function uses a whitelist of database tables that it is allowed
    to delete from. Otherwise you might end up deleting things like
    sale orders just because you want a view gone. Unless careful is
    set to False.
    """
    env.cr.execute(
        """
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
    """,
        [column_name, table_name],
    )
    result = env.cr.dictfetchall()
    for reference in result:
        env.cr.execute(
            "SELECT COUNT(*) FROM "
            + reference["table_name"]
            + " WHERE "
            + reference["column_name"]
            + " = %s",
            [id],
        )
        num_refs = env.cr.fetchone()[0]
        if num_refs > 0:
            if reference["is_nullable"] == "YES":
                logging.info(
                    "Setting %s to NULL on %s.",
                    reference["column_name"],
                    reference["table_name"],
                )
                env.cr.execute(
                    "UPDATE "
                    + reference["table_name"]
                    + " SET "
                    + reference["column_name"]
                    + " = NULL WHERE "
                    + reference["column_name"]
                    + " = %s",
                    [id],
                )
            else:
                logging.info(
                    "Deleting records on %s with %s set to %i",
                    reference["table_name"],
                    reference["column_name"],
                    id,
                )
                delete_record_by_column(
                    env, reference["table_name"], reference["column_name"], id, careful
                )


def delete_record_by_column(env, table_name, column_name, column_value, careful):
    if careful and not table_name in DESTRUCTION_TABLE_WHITELIST:
        raise UnresolvableForeignReferenceError(table_name, column_name, column_value)

    env.cr.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = %s AND column_name = 'id'",
        [table_name],
    )
    # If the table has an 'id' column, delete foreign references to this
    # first.
    if env.cr.dictfetchone():
        env.cr.execute(
            "SELECT id FROM " + table_name + " WHERE " + column_name + " = %s",
            [column_value],
        )
        ids = env.cr.dictfetchall()
        for row in ids:
            delete_table_references(env, table_name, "id", row["id"], careful)
    env.cr.execute(
        "DELETE FROM " + table_name + " WHERE " + column_name + " = %s", [column_value]
    )


def purge_model(env, model_id, careful=True):
    def unlink_model():
        env.cr.rollback()
        # Always works, but is VERY slow:
        delete_table_references(env, "ir_model", "id", model_id, careful)
        env.cr.execute("DELETE FROM ir_model WHERE id = %s", [model_id])

    env.cr.execute("SELECT model FROM ir_model WHERE id = %s", [model_id])
    model_name = env.cr.fetchone()[0]
    env.cr.commit()
    try:
        env.cr.execute(
            "DELETE FROM ir_cron WHERE ir_actions_server_id IN ("
            "SELECT id FROM ir_act_server WHERE model_id = %s"
            ")",
            [model_id],
        )
        env.cr.execute("DELETE FROM ir_act_server WHERE model_id = %s", [model_id])
        env.cr.execute("DELETE FROM ir_model_access WHERE model_id = %s", [model_id])
        env.cr.execute("DELETE FROM ir_model_constraint WHERE model = %s", [model_id])
        env.cr.execute(
            "DELETE FROM ir_model_fields WHERE model_id = %s OR relation = %s",
            [model_id, model_name],
        )
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
            delete_table_references(env, "ir_ui_view", "id", view_id)
        except UnresolvableForeignReferenceError as e:
            logging.info(
                "Warning: unable to delete view %i: there is a foreign "
                "reference with table %s (column %s = %s), which can't just "
                "be deleted. Skipping this view for now..."
                % (view_id, e.table_name, e.column_name, str(e.column_value))
            )
            return False
        env.cr.execute("DELETE FROM ir_ui_view WHERE id = %s", [view_id])

    env.cr.execute("SELECT id FROM ir_ui_view WHERE inherit_id = %s", [view_id])
    result = env.cr.dictfetchall()
    for child in result:
        purge_view(env, child["id"])

    logging.info("Deleting view %i..." % view_id)
    env.cr.execute("DELETE FROM ir_ui_view_group_rel WHERE view_id = %s", [view_id])
    try:
        env.cr.execute("DELETE FROM ir_ui_view WHERE id = %s", [view_id])
    except psycopg2.errors.ForeignKeyViolation:
        unlink_view()
    except psycopg2.errors.NotNullViolation:
        unlink_view()
    env.cr.execute(
        "DELETE FROM ir_model_data WHERE model = 'ir.ui.view' AND res_id = %s",
        [view_id],
    )
    env.cr.commit()
    return True
