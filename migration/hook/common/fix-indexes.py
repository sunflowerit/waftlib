#!.venv/bin/click-odoo
import logging
from enum import IntEnum

logger = logging.getLogger("index_checker")

INDEXES_TO_CHECK = {
    "base": [
        "ir_attachment_res_idx",
        "ir_model_data_model_res_id_index",
        "ir_ui_view_custom_user_id_ref_id",
        "ir_ui_view_model_type_inherit_id",
    ],
    "crm": [
        "crm_lead_user_id_team_id_type_index",
        "crm_lead_create_date_team_id_idx",
    ],
    "account": [
        "account_move_line_partner_id_ref_idx",
        "account_move_line_date_name_id_idx",
    ],
    "sale": [
        "sale_order_date_order_id_idx",
    ],
    "project": [
        "mail_tracking_value_mail_message_id_old_value_integer_task_stage",
        "mail_message_date_res_id_id_for_burndown_chart",
    ],
    "hr_work_entry": [
        "hr_work_entry_date_start_date_stop_index",
    ],
    "hr_leave": [
        "hr_leave_date_to_date_from_index",
    ],
    "l10n_in": [
        "account_move_line_move_product_index",
    ],
}


def index_exists(cr, indexname):
    """Return whether the given index exists."""
    cr.execute("SELECT 1 FROM pg_indexes WHERE indexname=%s", (indexname,))
    return cr.rowcount


class FunctionStatus(IntEnum):
    MISSING = 0  # function is not present (falsy)
    PRESENT = 1  # function is present but not indexable (not immutable)
    INDEXABLE = 2  # function is present and indexable (immutable)


def get_max_identifier_length(cr):
    cr.execute("SHOW max_identifier_length")
    return cr.fetchall()[0][0]


def has_unaccent(cr):
    """Test whether the database has function 'unaccent' and return its status.

    The unaccent is supposed to be provided by the PostgreSQL unaccent contrib
    module but any similar function will be picked by OpenERP.

    :rtype: FunctionStatus
    """
    cr.execute(
        """
        SELECT p.provolatile
        FROM pg_proc p
            LEFT JOIN pg_catalog.pg_namespace ns ON p.pronamespace = ns.oid
        WHERE p.proname = 'unaccent'
              AND p.pronargs = 1
              AND ns.nspname = 'public'
    """
    )
    result = cr.fetchone()
    if not result:
        return FunctionStatus.MISSING
    # The `provolatile` of unaccent allows to know whether the unaccent function
    # can be used to create index (it should be 'i' - means immutable), see
    # https://www.postgresql.org/docs/current/catalog-pg-proc.html.
    return FunctionStatus.INDEXABLE if result[0] == "i" else FunctionStatus.PRESENT


def has_trigram(cr):
    """Test if the database has the a word_similarity function.

    The word_similarity is supposed to be provided by the PostgreSQL built-in
    pg_trgm module but any similar function will be picked by Odoo.

    """
    cr.execute("SELECT proname FROM pg_proc WHERE proname='word_similarity'")
    return len(cr.fetchall()) > 0


def generate_index_expr(
    cr, indexname, tablename, expressions, method="btree", where=""
):
    """Generate index expression"""
    args = ", ".join(expressions)
    if where:
        where = f" WHERE ({where})"
    return (
        f"CREATE INDEX {indexname} ON public.{tablename} USING {method} ({args}){where}"
    )


def get_index_expr(cr, indexname):
    cr.execute("SELECT indexdef FROM pg_indexes WHERE indexname = %s", (indexname,))
    return cr.fetchone()[0]


def get_unaccent_wrapper(x):
    return "unaccent(({})::text)".format(x)


# check extensions
has_unaccent = has_unaccent(env.cr)
if not has_unaccent:
    logger.warning("Unaccent extension missing")
has_trigram = has_trigram(env.cr)
if not has_trigram:
    logger.warning("Trigram extension missing")

# check unaccent status
if not has_unaccent == FunctionStatus.INDEXABLE:
    logger.warn(
        "PostgreSQL function 'unaccent' is present but not immutable, "
        "therefore trigram indexes may not be effective.",
    )

# check manual indexes
for module, indexes in INDEXES_TO_CHECK.items():
    logger.debug("Checking deviant indexes for module %s", module)
    if not env["ir.module.module"].search([("name", "=", module)]).state == "installed":
        continue
    for index in indexes:
        if index_exists(env.cr, index):
            logger.debug("%s is there", index)
        else:
            logger.warning("%s IS NOT THERE", index)

# check automatic indexes
model_names = [m for m in env]
max_len = int(get_max_identifier_length(env.cr))
expected = [
    (
        f"{Model._table}_{field.name}_index"[:max_len],
        Model._table,
        field,
        getattr(field, "unaccent", False),
    )
    for model_name in model_names
    for Model in [env[model_name]]
    if Model._auto and not Model._abstract
    for field in Model._fields.values()
    if field.column_type and field.store
]
env.cr.execute(
    "SELECT indexname, tablename FROM pg_indexes WHERE indexname IN %s",
    [tuple(row[0] for row in expected)],
)
existing = dict(env.cr.fetchall())
for indexname, tablename, field, unaccent in expected:
    column_expression = f"{field.name}"
    index = field.index

    # check index type
    assert index in ("btree", "btree_not_null", "trigram", True, False, None)

    # check missing index
    if (
        index
        and indexname not in existing
        and (
            (not field.translate and index != "trigram")
            or (index == "trigram" and has_trigram)
        )
    ):
        logger.warning("Missing index %s", indexname)

    # check index definition
    if index and (
        (not field.translate and index != "trigram")
        or (index == "trigram" and has_trigram)
    ):
        if index == "trigram":
            if field.translate:
                column_expression = f"""(jsonb_path_query_array({column_expression}, '$.*'::jsonpath)::text)"""
            # add `unaccent` to the trigram index only because the
            # trigram indexes are mainly used for (i/=)like search and
            # unaccent is added only in these cases when searching
            if unaccent and has_unaccent:
                if has_unaccent == FunctionStatus.INDEXABLE:
                    column_expression = get_unaccent_wrapper(column_expression)
            expression = f"{column_expression} gin_trgm_ops"
            method = "gin"
            where = ""
        else:  # index in ['btree', 'btree_not_null'， True]
            expression = f"{column_expression}"
            method = "btree"
            where = (
                f"{column_expression} IS NOT NULL" if index == "btree_not_null" else ""
            )
        expr = get_index_expr(env.cr, indexname)
        expected_expr = generate_index_expr(
            env.cr, indexname, tablename, [expression], method, where
        )
        if expr != expected_expr:
            logger.warning("Index not as expected!")
            logger.warning(f"Used index: {expr}")
            logger.warning(f"Expected index: {expected_expr}")
            env.cr.execute(f"DROP INDEX {indexname}")
            env.cr.execute(expected_expr)

# check automatic _rel indexes
# TODO
