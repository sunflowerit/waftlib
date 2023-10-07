#!/usr/bin/env python
# Version: v.23.08.03
# -*- coding: utf-8 -*-

from dotenv import load_dotenv
from glob import glob
import logging
import os
from subprocess import check_output, check_call, run, PIPE
import yaml
try:
    from shutil import which
except ImportError:
    # Custom which implementation for Python 2
    def which(binary):
        return check_output(["which", binary]).strip()

SCRIPT_PATH = os.path.abspath(os.path.dirname(__file__))
ODOO_WORK_DIRECTORY = os.path.realpath(os.path.join(SCRIPT_PATH, "../../../../.."))
os.environ['ODOO_WORK_DIRECTORY'] = ODOO_WORK_DIRECTORY
load_dotenv(os.path.join(ODOO_WORK_DIRECTORY, "config/env-default"))
load_dotenv(os.path.join(ODOO_WORK_DIRECTORY, "config/env-shared"), override=True)
load_dotenv(os.path.join(ODOO_WORK_DIRECTORY, ".env-secret"), override=True)

# Customize Waft logging
WAFT_LOG_LEVEL = os.environ["WAFT_LOG_LEVEL"]
logger = logging.getLogger("Waft")
log_handler = logging.StreamHandler()
log_formatter = logging.Formatter("%(name)s %(levelname)s: %(message)s")
log_handler.setFormatter(log_formatter)
logger.addHandler(log_handler)
if WAFT_LOG_LEVEL not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
    logger.warning("The 'WAFT_LOG_LEVEL' variable is incorrect; resetting to default WAFT_LOG_LEVEL='INFO'.")
    WAFT_LOG_LEVEL = 'INFO'
    os.environ["WAFT_LOG_LEVEL"] = 'INFO'
logger_level = getattr(logging, WAFT_LOG_LEVEL)

ODOO_ADMIN_PASSWORD = os.environ["ODOO_ADMIN_PASSWORD"]
if ODOO_ADMIN_PASSWORD == '':
    logger.warning("The 'ODOO_ADMIN_PASSWORD' variable is empty; resetting to default ODOO_ADMIN_PASSWORD='password'.")
    ODOO_ADMIN_PASSWORD = 'password'
    os.environ["ODOO_ADMIN_PASSWORD"] = 'password'

ODOO_DBFILTER = os.environ["ODOO_DBFILTER"]
if ODOO_DBFILTER == '':
    logger.warning("The 'ODOO_DBFILTER' variable is empty; resetting to default ODOO_DBFILTER='.*'.")
    ODOO_DBFILTER = '.*'
    os.environ["ODOO_DBFILTER"] = '.*'

ODOO_INITIAL_LANG = os.environ["ODOO_INITIAL_LANG"]
if ODOO_INITIAL_LANG not in {
    'en_US', 'am_ET', 'ar_001', 'ar_SY', 'az_AZ', 'eu_ES', 'bn_IN', 'bs_BA', 'bg_BG', 'ca_ES', 'zh_CN', 'zh_HK', 'zh_TW',
    'hr_HR', 'cs_CZ', 'da_DK', 'nl_BE', 'nl_NL', 'en_AU', 'en_CA', 'en_GB', 'en_IN', 'et_EE', 'fi_FI', 'fr_BE', 'fr_CA',
    'fr_CH', 'fr_FR', 'gl_ES', 'ka_GE', 'de_DE', 'de_CH', 'el_GR', 'gu_IN', 'he_IL', 'hi_IN', 'hu_HU', 'id_ID', 'it_IT',
    'ja_JP', 'kab_DZ', 'km_KH', 'ko_KP', 'ko_KR', 'lo_LA', 'lv_LV', 'lt_LT', 'lb_LU', 'mk_MK', 'ml_IN', 'mn_MN', 'ms_MY',
    'my_MM', 'nb_NO', 'fa_IR', 'pl_PL', 'pt_AO', 'pt_BR', 'pt_PT', 'ro_RO', 'ru_RU', 'sr_RS', 'sr@latin', 'sk_SK', 'sl_SI',
    'es_AR', 'es_BO', 'es_CL', 'es_CO', 'es_CR', 'es_DO', 'es_EC', 'es_GT', 'es_MX', 'es_PA', 'es_PE', 'es_PY', 'es_UY',
    'es_VE', 'es_ES', 'sv_SE', 'th_TH', 'tl_PH', 'tr_TR', 'uk_UA', 'vi_VN', 'sq_AL', 'te_IN'
    }:
    logger.warning("The 'ODOO_INITIAL_LANG' variable is not in the standard languages list; resetting to default ODOO_INITIAL_LANG='nl_NL'.")
    ODOO_INITIAL_LANG = 'nl_NL'
    os.environ["ODOO_INITIAL_LANG"] = 'nl_NL'

ODOO_LIMIT_MEMORY_HARD = os.environ["ODOO_LIMIT_MEMORY_HARD"]
if not ODOO_LIMIT_MEMORY_HARD.isdigit():
    logger.warning("The 'ODOO_LIMIT_MEMORY_HARD' variable is incorrect; resetting to default ODOO_LIMIT_MEMORY_HARD='2684354560'.")
    ODOO_LIMIT_MEMORY_HARD = '2684354560'
    os.environ["ODOO_LIMIT_MEMORY_HARD"] = '2684354560'

ODOO_LIMIT_MEMORY_SOFT = os.environ["ODOO_LIMIT_MEMORY_SOFT"]
if not ODOO_LIMIT_MEMORY_SOFT.isdigit():
    logger.warning("The 'ODOO_LIMIT_MEMORY_SOFT' variable is incorrect; resetting to default ODOO_LIMIT_MEMORY_SOFT='2147483648'.")
    ODOO_LIMIT_MEMORY_SOFT = '2147483648'
    os.environ["ODOO_LIMIT_MEMORY_SOFT"] = '2147483648'

ODOO_LIST_DB = os.environ["ODOO_LIST_DB"]
if ODOO_LIST_DB.lower() not in {"true", "false"}:
    logger.warning("The 'ODOO_LIST_DB' variable is incorrect; resetting to default ODOO_LIST_DB='false'.")
    ODOO_LIST_DB = 'false'
    os.environ["ODOO_LIST_DB"] = 'false'

ODOO_UNACCENT = os.environ["ODOO_UNACCENT"]
if ODOO_UNACCENT.lower() not in {"true", "false"}:
    logger.warning("The 'ODOO_UNACCENT' variable is incorrect; resetting to default ODOO_UNACCENT='false'.")
    ODOO_UNACCENT = 'false'
    os.environ["ODOO_UNACCENT"] = 'false'

ODOO_VERSION = os.environ["ODOO_VERSION"]
if ODOO_VERSION not in {'8.0', '9.0', '10.0', '11.0', '12.0', '13.0', '14.0', '15.0', '16.0'}:
    logger.error("The 'ODOO_VERSION' variable is incorrect!")
    exit(1)

ODOO_WITHOUT_DEMO = os.environ["ODOO_WITHOUT_DEMO"]
if ODOO_WITHOUT_DEMO == '':
    logger.warning("The 'ODOO_WITHOUT_DEMO' variable is empty; resetting to default ODOO_WITHOUT_DEMO='all'.")
    ODOO_WITHOUT_DEMO = 'all'
    os.environ["ODOO_WITHOUT_DEMO"] = 'all'

ODOO_WORKERS = os.environ["ODOO_WORKERS"]
if not ODOO_WORKERS.isdigit():
    logger.warning("The 'ODOO_WORKERS' variable is incorrect; resetting to default ODOO_WORKERS='0'.")
    ODOO_WORKERS = '0'
    os.environ["ODOO_WORKERS"] = '0'

PGDATABASE = os.environ["PGDATABASE"]
if PGDATABASE == '':
    logger.warning("The 'PGDATABASE' variable is empty; resetting to default PGDATABASE='odoodatabase'.")
    PGDATABASE = 'odoodatabase'
    os.environ["PGDATABASE"] = 'odoodatabase'

PGHOST = os.environ["PGHOST"]
if PGHOST == '':
    logger.warning("The 'PGHOST' variable is empty; resetting to default PGHOST='localhost'.")
    PGHOST = 'localhost'
    os.environ["PGHOST"] = 'localhost'

PGPASSWORD = os.environ["PGPASSWORD"]

PGPORT = os.environ["PGPORT"]
if not PGPORT.isdigit():
    logger.warning("The 'PGPORT' variable is incorrect; resetting to default PGPORT='5432'.")
    PGPORT = '5432'
    os.environ["PGPORT"] = '5432'

PGUSER = os.environ["PGUSER"]
if PGUSER == '':
    logger.warning("The 'PGUSER' variable is incorrect; resetting to default PGUSER='odoo'.")
    PGUSER = 'odoo'
    os.environ["PGUSER"] = 'odoo'

WAFT_CLEAN = os.environ["WAFT_CLEAN"]
if WAFT_CLEAN.lower() not in {"true", "false"}:
    logger.warning("The 'WAFT_CLEAN' variable is incorrect; resetting to default WAFT_CLEAN='false'.")
    WAFT_CLEAN = 'false'
    os.environ["WAFT_CLEAN"] = 'false'

WAFT_COMPILE = os.environ["WAFT_COMPILE"]
if WAFT_COMPILE.lower() not in {"true", "false"}:
    logger.warning("The 'WAFT_COMPILE' variable is incorrect; resetting to default WAFT_COMPILE='true'.")
    WAFT_COMPILE = 'true'
    os.environ["WAFT_COMPILE"] = 'true'

WAFT_DEPTH_DEFAULT = os.environ["WAFT_DEPTH_DEFAULT"]
if not WAFT_DEPTH_DEFAULT.isdigit():
    logger.warning("The 'WAFT_DEPTH_DEFAULT' variable is incorrect; resetting to default WAFT_DEPTH_DEFAULT='1'.")
    WAFT_DEPTH_DEFAULT = '1'
    os.environ["WAFT_DEPTH_DEFAULT"] = '1'

WAFT_DEPTH_MERGE = os.environ["WAFT_DEPTH_MERGE"]
if not WAFT_DEPTH_MERGE.isdigit():
    logger.warning("The 'WAFT_DEPTH_MERGE' variable is incorrect; resetting to default WAFT_DEPTH_MERGE='100'.")
    WAFT_DEPTH_MERGE = '100'
    os.environ["WAFT_DEPTH_MERGE"] = '100'

WAFT_WAIT_DB = os.environ["WAFT_WAIT_DB"]
if WAFT_WAIT_DB.lower() not in {"true", "false"}:
    logger.warning("The 'WAFT_WAIT_DB' variable is incorrect; resetting to default WAFT_WAIT_DB='false'.")
    WAFT_WAIT_DB = 'false'
    os.environ["WAFT_WAIT_DB"] = 'false'

CODE_ODOO_DIRECTORY = os.path.join(ODOO_WORK_DIRECTORY, "odoo-code")
ADDONS_YAML_FILE = os.path.join(ODOO_WORK_DIRECTORY, "config/addons.yaml")
CODE_ODOO_YAML_FILE = os.path.join(ODOO_WORK_DIRECTORY, "config/odoo-code.yaml")
ODOO_MAIN_CODE_PATH = os.path.join(ODOO_WORK_DIRECTORY, "odoo-code/odoo")
ADDONS_AUTO_DIRECTORY = os.path.join(ODOO_WORK_DIRECTORY, ".ignore/auto/addons")

if not os.path.exists(CODE_ODOO_YAML_FILE):
    logger.error("Could not find '%s' Odoo code configuration file.", CODE_ODOO_YAML_FILE)
    exit(1)

try:
    with open(CODE_ODOO_YAML_FILE) as code_ODOO_YAML_file:
        code_odoo_yaml_file = yaml.safe_load(code_ODOO_YAML_file)
except IOError:
    logger.error("Could not load '%s' Odoo code configuration file.", CODE_ODOO_YAML_FILE)
    exit(1)

if not os.path.exists(ADDONS_YAML_FILE):
    logger.error("Could not find '%s' addons configuration yaml.", ADDONS_YAML_FILE)
    exit(1)

try:
    with open(ADDONS_YAML_FILE) as addons_YAML_file:
        addons_yaml_file = yaml.safe_load(addons_YAML_file)
except IOError:
    logger.error("Could not load '%s' addons configuration yaml.", ADDONS_YAML_FILE)
    exit(1)

class AddonsConfigError(Exception):
    def __init__(self, message, *args):
        super(AddonsConfigError, self).__init__(message, *args)
        self.message = message

def addons_config(strict_running=False):
    """
    Yield addon name and path from ``ADDONS_YAML_FILE``.

    :'strict_running' boolean parameter:
        Use ``True`` to raise an exception if any declared addon is not found.

    :return Iterator[str, str]:
        A generator that yields ``(addon, repository/addon)`` pairs.
    """
    addons_info = dict()
    addons_missing_paths = set()
    addons_missing_manifest_paths = set()
    # Add default values for special sections
    addons_repositories_paths = {}
    addons_repositories_paths.setdefault("odoo/addons", {"*"})
    addons_repositories_paths.setdefault("enterprise", {"*"})
    addons_repositories_paths.setdefault("private", {"*"})
    for addons_repository_path in code_odoo_yaml_file:
        addons_repositories_paths.setdefault(addons_repository_path , "*")
    # Flatten all sections in a single dict
    for addons_repository_path, addons_partial_paths in addons_yaml_file:
        logger.debug("Processing %s repository", addons_repository_path)
        addons_repositories_paths[addons_repository_path] = addons_partial_paths
    logger.debug("Merged addons definition before expanding: %r", addons_repositories_paths)
    # Expand all addons paths and store config
    for addons_repository_path, addons_partial_paths in addons_repositories_paths.items():
        for addon_partial_path in addons_partial_paths:
            logger.debug("Expanding in repository %s addon path %s", addons_repository_path, addon_partial_path)
            addon_partial_full_path = os.path.join(CODE_ODOO_DIRECTORY, addons_repository_path, addon_partial_path)
            addon_found_path = glob(addon_partial_full_path)
            if not addon_found_path:
                # Projects without enterprise addons should never fail
                if (addons_repository_path, addon_partial_path) != ("enterprise", "*"):
                    addons_missing_paths.add(addon_partial_full_path)
                logger.debug("Skipping unexpandable addon path '%s'", addon_partial_full_path)
                continue
            if not addon_found_path:
                # Projects without private addons should never fail
                if (addons_repository_path, addon_partial_path) != ("private", "*"):
                    addons_missing_paths.add(addon_partial_full_path)
                logger.debug("Skipping unexpandable addon path '%s'", addon_partial_full_path)
                continue
            for addon_full_path in addon_found_path:
                if not os.path.isdir(addon_full_path):
                    continue
                manifests = (os.path.join(addon_full_path, manifest_file_name) for manifest_file_name in ("__manifest__.py", "__openerp__.py"))
                if not any(os.path.isfile(manifest_file_name) for manifest_file_name in manifests):
                    addons_missing_manifest_paths.add(addon_full_path)
                    logger.debug("Skipping '%s' as it is not a valid Odoo module.", addon_full_path)
                    continue
                logger.debug("Registering addon %s", addon_full_path)
                addon_name = os.path.basename(addon_full_path)
                addons_info.setdefault(addon_name, set())
                addons_info[addon_name].add(addons_repository_path)
    if strict_running:
        missing_error = []
        if addons_missing_paths:
            missing_error += ["Addons not found:", pformat(addons_missing_paths)]
        if addons_missing_manifest_paths:
            missing_error += ["Addons without manifest:", pformat(addons_missing_manifest_paths)]
        if missing_error:
            raise AddonsConfigError("\n".join(missing_error), addons_missing_paths, addons_missing_manifest_paths)
    logger.debug("Resulting configuration after expanding: %r", addons_info)
    for addon_name, addons_repository_path in addons_info.items():
        # Enterprise addons are most important
        if addons_repository_path == "enterprise":
            yield addon_name, "enterprise"
            continue
        # Private addons are most important
        if addons_repository_path == "private":
            yield addon_name, "private"
            continue
        # Odoo core addons are least important
        if addons_repository_path == {"odoo/addons"}:
            yield addon_name, "odoo/addons"
            continue
        addons_repository_path.discard("odoo/addons")
        # Other addons fall in between
        if len(addons_repository_path) != 1:
            raise AddonsConfigError(
                "Addon {} defined in several repositories {}".format(addon_name, addons_repository_path)
            )
        for addons_repository_item_path in addons_repository_path:
            yield addon_name, addons_repository_item_path
