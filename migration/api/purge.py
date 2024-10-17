from psycopg2.extensions import AsIs
import logging


class Purger:
    def __init__(self, cr, table_name, reset_id=None):
        self.clean_foreign_references = False
        self.cr = cr
        self.filter_operator = None
        self.filter_record_id = None
        self.table_name = table_name
        self.columns_already_cleaned = []
        self.reset_id = reset_id

        self.constraints = fetch_foreign_key_constraints(self.cr, self.table_name)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, type, value, traceback):
        self.stop()

    def _clean_foreign_references(
        self, constraint_name, foreign_table_name, foreign_column, is_nullable
    ):
        """Cleans up any foreign references to our table, recursively."""
        delete = False
        update_value = self.reset_id
        if self.reset_id or is_nullable:
            logging.info(
                "Resetting foreign references to %s from %s.%s to %s."
                % (self.reset_id, foreign_table_name, foreign_column, self.table_name)
            )
        else:
            if self.reset_id == None:
                delete = True
                logging.info(
                    "Deleting foreign references from %s.%s to %s."
                    % (foreign_table_name, foreign_column, self.table_name)
                )

        if not self.filter_record_id:
            filter_clause = '\"%s\" IS NOT NULL AND \"%s\" NOT IN (SELECT id FROM "%s")' % (foreign_column, foreign_column, self.table_name)
        else:
            filter_clause = "\"%s\" %s %s" % (foreign_column, self.filter_operator, self.filter_record_id)
        if not delete:
            self.cr.execute(
                'CREATE INDEX IF NOT EXISTS "%s_temp_index" ON "%s" ("%s")'
                % (constraint_name, foreign_table_name, foreign_column)
            )
            query = """
                UPDATE \"%s\" SET \"%s\" = %s WHERE %s
            """ % (
                foreign_table_name,
                foreign_column,
                "%s",
                filter_clause,
            )
            logging.info(query, update_value)
            self.cr.execute(
                query,
                [update_value],
            )
            self.cr.execute('DROP INDEX IF EXISTS "%s_temp_index"' % constraint_name)
        else:
            if not (foreign_table_name, foreign_column) in self.columns_already_cleaned:
                self.columns_already_cleaned.append(
                    (foreign_table_name, foreign_column)
                )
                self.cr.execute(
                    'CREATE INDEX IF NOT EXISTS "%s_temp_index" ON "%s" ("%s")'
                    % (constraint_name, foreign_table_name, foreign_column)
                )
                purger = Purger(self.cr, foreign_table_name)
                purger.start()
                purger.purge(filter_clause)
                purger.clean()
                # Only clean, don't stop, because foreign_table_name might be the same as self.table_name, and we don't want to enable the foreign keys too early
                self.cr.execute(
                    'DROP INDEX IF EXISTS "%s_temp_index"' % constraint_name
                )
            else:
                raise Exception(
                    "Recursion detected while cleaning foreign references. Column %s.%s was encountered twice."
                    % (foreign_table_name, foreign_column)
                )

    def clean(self):
        logging.info("Cleaning foreign references to %s..." % self.table_name)
        for (
            constraint_name,
            foreign_table_name,
            foreign_column,
            is_nullable,
        ) in self.constraints:
            if self.clean_foreign_references:
                self._clean_foreign_references(
                    constraint_name, foreign_table_name, foreign_column, is_nullable
                )
        self.clean_foreign_references = False

    def purge(self, where_clause):
        query = "DELETE FROM %s WHERE " + where_clause
        logging.info(query, AsIs(self.table_name))
        self.cr.execute(query, [AsIs(self.table_name)])
        self.clean_foreign_references = self.cr.rowcount > 0

    def purge_minmax(self, where_clause, filter=None):
        filter_opposites = {"min": "max", "max": "min"}
        filter_operators = {
            "min": "<",
            "max": ">",
        }
        if filter:
            logging.info("Searching flip-over ID for purging " + where_clause)
            filter_opposite = filter_opposites[filter]
            self.cr.execute(
                'SELECT %s(id) FROM "%s" WHERE %s'
                % (filter_opposite, self.table_name, where_clause)
            )
            result = self.cr.fetchone()
            self.filter_record_id = result[0]
            self.filter_operator = filter_operators[filter]
        actual_where_clause = (
            "id %s %s" % (self.filter_operator, self.filter_record_id)
            if self.filter_operator and self.filter_record_id
            else where_clause
        )

        self.purge(actual_where_clause)

    def start(self):
        logging.info("Disabling triggers for table %s", self.table_name)
        self.cr.execute("ALTER TABLE %s DISABLE TRIGGER ALL", [AsIs(self.table_name)])

    def stop(self):
        if self.clean_foreign_references:
            for (
                constraint_name,
                foreign_table_name,
                foreign_column,
                is_nullable,
            ) in self.constraints:
                logging.info("Cleaning foreign references to %s..." % self.table_name)
                self._clean_foreign_references(
                    constraint_name, foreign_table_name, foreign_column, is_nullable
                )

                logging.info(
                    "Enabling foreign key constraint %s from table %s again..."
                    % (constraint_name, foreign_table_name)
                )
                self.cr.execute(
                    """
                    UPDATE pg_constraint SET convalidated = FALSE WHERE conname = %s
                """,
                    [constraint_name],
                )
                self.cr.execute(
                    "ALTER TABLE %s VALIDATE CONSTRAINT %s",
                    [AsIs(foreign_table_name), AsIs(constraint_name)],
                )
        self.clean_foreign_references = False

    def truncate(self):
        logging.info("Truncating table %s", self.table_name)
        self.cr.execute("TRUNCATE %s", [AsIs(self.table_name)])
        self.cr.rowcount


class UnresolvableForeignReferenceError(Exception):
    def __init__(self, table_name, column_name, column_value):
        self.table_name = table_name
        self.column_name = column_name
        self.column_value = column_value


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
    constrains = [
        (
            r["constraint_name"],
            r["table_name"],
            r["column_name"],
            r["is_nullable"] == "YES",
        )
        for r in results
    ]
    # Put constrains that are from the table itself, at the end, so that they are processed the last
    constrains.sort(key=lambda x: x[1] == table_name)
    return constrains


def purge_records(cr, table_name, where_clause, reset_id, non_updatable_tables=[]):
    with Purger(cr, table_name):
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


def purge_model(env, model_id, careful=True):
    env.cr.execute("SELECT model FROM ir_model WHERE id = %s", [model_id])
    model_name = env.cr.fetchone()[0]
    env.cr.commit()
    env.cr.execute(
        """
        DELETE FROM ir_cron WHERE ir_actions_server_id IN (
            SELECT id FROM ir_act_server WHERE model_id = %s
        )
    """,
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


def purge_view(env, view_id):
    def unlink_view():
        env.cr.rollback()
        try:
            purge_records(env.cr, "ir_ui_view", "id = " + str(view_id))
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
