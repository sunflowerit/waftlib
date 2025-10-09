from psycopg2.extensions import AsIs
import logging


_logger = logging.getLogger(__name__)


class Purger:
    def __init__(
        self,
        cr,
        table_name,
        reset_id=None,
        skip_validation=False,
        delete_more_than_keep=False,
    ):
        self.clean_foreign_references = False
        self.cr = cr
        self.filter_operator = None
        self.filter_record_id = None
        self.table_name = table_name
        self.columns_already_cleaned = []
        self.reset_id = reset_id
        self.skip_validation = skip_validation
        self.delete_more_than_keep = delete_more_than_keep

        self.constraints = fetch_foreign_key_constraints(self.cr, self.table_name)
        self.has_id = self._has_id()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, type, value, traceback):
        self.stop()

    def _clean_foreign_reference(
        self, constraint_name, foreign_table_name, foreign_column, is_nullable
    ):
        """Cleans up any foreign references to our table, recursively."""
        delete = False
        update_value = self.reset_id
        if not self.table_name.endswith("_rel") and (self.reset_id or is_nullable):
            _logger.debug(
                "Resetting foreign references to %s from %s.%s to %s."
                % (self.reset_id, foreign_table_name, foreign_column, self.table_name)
            )
        else:
            delete = True
            _logger.debug(
                "Deleting foreign references from %s.%s to %s."
                % (foreign_table_name, foreign_column, self.table_name)
            )

        if not self.filter_record_id:
            if self.delete_more_than_keep or not self.has_id:
                filter_clause = (
                    '"%s" IS NOT NULL AND "%s" NOT IN (SELECT id FROM "%s")'
                    % (
                        foreign_column,
                        foreign_column,
                        self.table_name,
                    )
                )
            else:
                filter_clause = (
                    '"%s" IS NOT NULL AND "%s" IN (SELECT id FROM "%s_deleted")'
                    % (
                        foreign_column,
                        foreign_column,
                        self.table_name,
                    )
                )
        else:
            filter_clause = '"%s" %s %s' % (
                foreign_column,
                self.filter_operator,
                self.filter_record_id,
            )
        if not delete:
            _logger.debug(
                "Creating index to on %s.%s to speed up update...",
                foreign_table_name,
                foreign_column,
            )
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
            _logger.debug(query, update_value)
            self.cr.execute(
                query,
                [update_value],
            )
            _logger.debug("%s records affected.", self.cr.rowcount)
            self.cr.execute('DROP INDEX IF EXISTS "%s_temp_index"' % constraint_name)
        else:
            if not (foreign_table_name, foreign_column) in self.columns_already_cleaned:
                self.columns_already_cleaned.append(
                    (foreign_table_name, foreign_column)
                )
                _logger.debug(
                    "Creating index to on %s.%s to speed up deletion...",
                    foreign_table_name,
                    foreign_column,
                )
                self.cr.execute(
                    'CREATE INDEX IF NOT EXISTS "%s_temp_index" ON "%s" ("%s")'
                    % (constraint_name, foreign_table_name, foreign_column)
                )
                purger = Purger(self.cr, foreign_table_name, delete_more_than_keep=self.delete_more_than_keep, skip_validation=self.skip_validation)
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
        _logger.debug("Cleaning foreign references to %s..." % self.table_name)
        for (
            constraint_name,
            foreign_table_name,
            foreign_column,
            is_nullable,
        ) in self.constraints:
            if self.clean_foreign_references:
                self._clean_foreign_reference(
                    constraint_name, foreign_table_name, foreign_column, is_nullable
                )
        if not self.delete_more_than_keep and self.has_id:
            self.cr.execute('DROP TABLE "%s_deleted"' % self.table_name)
        self.clean_foreign_references = False

    def _has_id(self):
        self.cr.execute(
            """
            SELECT * FROM information_schema.columns
            WHERE table_name = %s and column_name = 'id'
        """,
            [self.table_name],
        )
        return self.cr.rowcount > 0

    def purge(self, where_clause):
        if self.delete_more_than_keep or not self.has_id:
            query = "DELETE FROM %s WHERE " + where_clause
        else:
            self.cr.execute(
                'CREATE TABLE "%s_deleted" (id INTEGER NOT NULL PRIMARY KEY)'
                % self.table_name
            )
            query = """
                WITH deleted AS (
                    DELETE FROM %s WHERE %s
                    RETURNING id
                )
                INSERT INTO "%s_deleted" SELECT id FROM deleted
            """ % (
                "%s",
                where_clause,
                self.table_name,
            )
        _logger.debug(query, AsIs(self.table_name))
        self.cr.execute(query, [AsIs(self.table_name)])
        _logger.debug("%s rows deleted.", self.cr.rowcount)
        self.clean_foreign_references = self.cr.rowcount > 0

    def purge_minmax(self, where_clause, filter=None):
        filter_opposites = {"min": "max", "max": "min"}
        filter_operators = {
            "min": "<",
            "max": ">",
        }
        if filter:
            _logger.debug("Searching flip-over ID for purging " + where_clause)
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
        _logger.debug("Disabling triggers for table %s", self.table_name)
        self.cr.execute("ALTER TABLE %s DISABLE TRIGGER ALL", [AsIs(self.table_name)])

    def stop(self):
        if self.clean_foreign_references:
            _logger.debug("Cleaning foreign references to %s..." % self.table_name)
            for (
                constraint_name,
                foreign_table_name,
                foreign_column,
                is_nullable,
            ) in self.constraints:
                self._clean_foreign_reference(
                    constraint_name, foreign_table_name, foreign_column, is_nullable
                )

                if not self.skip_validation:
                    _logger.debug(
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
        if not self.delete_more_than_keep and self.has_id:
            self.cr.execute('DROP TABLE "%s_deleted"' % self.table_name)
        self.clean_foreign_references = False

    def truncate(self):
        _logger.debug("Truncating table %s", self.table_name)
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
        _logger.debug(query)
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
            _logger.debug(query)
            cr.execute(query)
        _logger.debug("DROP TABLE yyy")
        cr.execute("DROP TABLE yyy")


def purge_model(env, model_id, careful=True, model_name=None):
    env.cr.execute("SELECT model FROM ir_model WHERE id = %s", [model_id])
    if not model_name:
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


def purge_model_by_name(env, model_name, careful=True):
    env.cr.execute("SELECT id FROM ir_model WHERE model = %s", [model_name])
    result = env.cr.fetchone()
    if result:
        model_id = result[0]
        purge_model(env, model_id, careful, model_name)
    else:
        logging.warning("Unable to purge model %s, model was not found", model_name)


def purge_view(env, view_id):
    def unlink_view():
        env.cr.rollback()
        try:
            purge_records(env.cr, "ir_ui_view", "id = " + str(view_id))
        except UnresolvableForeignReferenceError as e:
            _logger.debug(
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

    _logger.debug("Deleting view %i..." % view_id)
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
