#!/usr/bin/env python
# Version: v.23.08.03
# -*- coding: utf-8 -*-

from dotenv import load_dotenv
from glob import glob
from importlib import reload
import logging
import os
import re
from subprocess import check_output, check_call, run, PIPE
import yaml
from shutil import which

SCRIPT_PATH = os.path.abspath(os.path.dirname(__file__))
WORK_DIRECTORY = os.path.realpath(os.path.join(SCRIPT_PATH, "../../../../.."))
os.environ['WORK_DIRECTORY'] = WORK_DIRECTORY
CONFIGURATIONS_DIRECTORY = os.path.join(WORK_DIRECTORY, "config")
os.environ['CONFIGURATIONS_DIRECTORY'] = CONFIGURATIONS_DIRECTORY
load_dotenv(os.path.join(CONFIGURATIONS_DIRECTORY, "env-default"))
load_dotenv(os.path.join(CONFIGURATIONS_DIRECTORY, "env-shared"), override=True)
load_dotenv(os.path.join(WORK_DIRECTORY, ".env-secret"), override=True)

# Customize Waft logging
logging.shutdown()
reload(logging)
WAFT_LOG_LEVEL = os.environ["WAFT_LOG_LEVEL"]
logger = logging.getLogger("Waft")
log_handler = logging.StreamHandler()
log_formatter = logging.Formatter("%(name)s %(levelname)s: %(message)s")
log_handler.setFormatter(log_formatter)
logger.addHandler(log_handler)
if WAFT_LOG_LEVEL not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
    logger.warning(
        "The 'WAFT_LOG_LEVEL' variable is incorrect; resetting to default WAFT_LOG_LEVEL='INFO'."
        )
    WAFT_LOG_LEVEL = 'INFO'
    os.environ["WAFT_LOG_LEVEL"] = 'INFO'

logger_level = getattr(logging, WAFT_LOG_LEVEL)

ODOO_ADMIN_PASSWORD = os.environ["ODOO_ADMIN_PASSWORD"]
if ODOO_ADMIN_PASSWORD == '':
    logger.warning(
        "The 'ODOO_ADMIN_PASSWORD' variable is empty; resetting to default ODOO_ADMIN_PASSWORD='password'."
        )
    ODOO_ADMIN_PASSWORD = 'password'
    os.environ["ODOO_ADMIN_PASSWORD"] = 'password'

ODOO_DBFILTER = os.environ["ODOO_DBFILTER"]
if ODOO_DBFILTER == '':
    logger.warning(
        "The 'ODOO_DBFILTER' variable is empty; resetting to default ODOO_DBFILTER='.*'."
        )
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
    logger.warning(
        "The 'ODOO_INITIAL_LANG' variable is not in the standard languages list; resetting to default ODOO_INITIAL_LANG='nl_NL'."
        )
    ODOO_INITIAL_LANG = 'nl_NL'
    os.environ["ODOO_INITIAL_LANG"] = 'nl_NL'

ODOO_LIMIT_MEMORY_HARD = os.environ["ODOO_LIMIT_MEMORY_HARD"]
if not ODOO_LIMIT_MEMORY_HARD.isdigit():
    logger.warning(
        "The 'ODOO_LIMIT_MEMORY_HARD' variable is incorrect; resetting to default ODOO_LIMIT_MEMORY_HARD='2684354560'."
        )
    ODOO_LIMIT_MEMORY_HARD = '2684354560'
    os.environ["ODOO_LIMIT_MEMORY_HARD"] = '2684354560'

ODOO_LIMIT_MEMORY_SOFT = os.environ["ODOO_LIMIT_MEMORY_SOFT"]
if not ODOO_LIMIT_MEMORY_SOFT.isdigit():
    logger.warning(
        "The 'ODOO_LIMIT_MEMORY_SOFT' variable is incorrect; resetting to default ODOO_LIMIT_MEMORY_SOFT='2147483648'."
        )
    ODOO_LIMIT_MEMORY_SOFT = '2147483648'
    os.environ["ODOO_LIMIT_MEMORY_SOFT"] = '2147483648'

ODOO_LIST_DB = os.environ["ODOO_LIST_DB"]
if ODOO_LIST_DB.lower() not in {"true", "false"}:
    logger.warning(
        "The 'ODOO_LIST_DB' variable is incorrect; resetting to default ODOO_LIST_DB='false'."
        )
    ODOO_LIST_DB = 'false'
    os.environ["ODOO_LIST_DB"] = 'false'

ODOO_UNACCENT = os.environ["ODOO_UNACCENT"]
if ODOO_UNACCENT.lower() not in {"true", "false"}:
    logger.warning(
        "The 'ODOO_UNACCENT' variable is incorrect; resetting to default ODOO_UNACCENT='false'."
        )
    ODOO_UNACCENT = 'false'
    os.environ["ODOO_UNACCENT"] = 'false'

ODOO_VERSION = os.environ["ODOO_VERSION"]
if ODOO_VERSION not in {'8.0', '9.0', '10.0', '11.0', '12.0', '13.0', '14.0', '15.0', '16.0'}:
    logger.error(
        "The 'ODOO_VERSION' variable is incorrect!"
        )
    exit(1)

ODOO_WITHOUT_DEMO = os.environ["ODOO_WITHOUT_DEMO"]
if ODOO_WITHOUT_DEMO == '':
    logger.warning(
        "The 'ODOO_WITHOUT_DEMO' variable is empty; resetting to default ODOO_WITHOUT_DEMO='all'."
        )
    ODOO_WITHOUT_DEMO = 'all'
    os.environ["ODOO_WITHOUT_DEMO"] = 'all'

ODOO_WORKERS = os.environ["ODOO_WORKERS"]
if not ODOO_WORKERS.isdigit():
    logger.warning(
        "The 'ODOO_WORKERS' variable is incorrect; resetting to default ODOO_WORKERS='0'."
        )
    ODOO_WORKERS = '0'
    os.environ["ODOO_WORKERS"] = '0'

PGDATABASE = os.environ["PGDATABASE"]
if PGDATABASE == '':
    logger.warning(
        "The 'PGDATABASE' variable is empty; resetting to default PGDATABASE='odoodatabase'."
        )
    PGDATABASE = 'odoodatabase'
    os.environ["PGDATABASE"] = 'odoodatabase'

PGHOST = os.environ["PGHOST"]
if PGHOST == '':
    logger.warning(
        "The 'PGHOST' variable is empty; resetting to default PGHOST='localhost'."
        )
    PGHOST = 'localhost'
    os.environ["PGHOST"] = 'localhost'

PGPASSWORD = os.environ["PGPASSWORD"]

PGPORT = os.environ["PGPORT"]
if not PGPORT.isdigit():
    logger.warning(
        "The 'PGPORT' variable is incorrect; resetting to default PGPORT='5432'."
        )
    PGPORT = '5432'
    os.environ["PGPORT"] = '5432'

PGUSER = os.environ["PGUSER"]
if PGUSER == '':
    logger.warning(
        "The 'PGUSER' variable is incorrect; resetting to default PGUSER='odoo'."
        )
    PGUSER = 'odoo'
    os.environ["PGUSER"] = 'odoo'

WAFT_COMPILE = os.environ["WAFT_COMPILE"]
if WAFT_COMPILE.lower() not in {"true", "false"}:
    logger.warning(
        "The 'WAFT_COMPILE' variable is incorrect; resetting to default WAFT_COMPILE='true'."
        )
    WAFT_COMPILE = 'true'
    os.environ["WAFT_COMPILE"] = 'true'

WAFT_DEPTH_DEFAULT = os.environ["WAFT_DEPTH_DEFAULT"]
if not WAFT_DEPTH_DEFAULT.isdigit():
    logger.warning(
        "The 'WAFT_DEPTH_DEFAULT' variable is incorrect; resetting to default WAFT_DEPTH_DEFAULT='1'."
        )
    WAFT_DEPTH_DEFAULT = '1'
    os.environ["WAFT_DEPTH_DEFAULT"] = '1'

WAFT_DEPTH_MERGE = os.environ["WAFT_DEPTH_MERGE"]
if not WAFT_DEPTH_MERGE.isdigit():
    logger.warning(
        "The 'WAFT_DEPTH_MERGE' variable is incorrect; resetting to default WAFT_DEPTH_MERGE='100'."
        )
    WAFT_DEPTH_MERGE = '100'
    os.environ["WAFT_DEPTH_MERGE"] = '100'

WAFT_WAIT_DB = os.environ["WAFT_WAIT_DB"]
if WAFT_WAIT_DB.lower() not in {"true", "false"}:
    logger.warning(
        "The 'WAFT_WAIT_DB' variable is incorrect; resetting to default WAFT_WAIT_DB='false'."
        )
    WAFT_WAIT_DB = 'false'
    os.environ["WAFT_WAIT_DB"] = 'false'

REPOSITORIES_DIRECTORY = os.path.join(WORK_DIRECTORY, ".ignore/code")
CODE_YAML_FILE = os.path.join(CONFIGURATIONS_DIRECTORY, "code.yaml")
ODOO_MAIN_CODE_DIRECTORY = os.path.join(WORK_DIRECTORY, ".ignore/code/odoo")
IGNORE_DIRECTORY = os.path.join(WORK_DIRECTORY, ".ignore")
EVENTUAL_ADDONS_DIRECTORY = os.path.join(WORK_DIRECTORY, "addons")

# Check if CODE_YAML_FILE exist.
if not os.path.exists(CODE_YAML_FILE):
    logger.error(
        "Could not find '%s' Odoo code configuration file.",
        CODE_YAML_FILE
        )
    exit(1)

# Load CODE_YAML_FILE yaml file as code_file_yaml dictionary.
try:
    with open(CODE_YAML_FILE) as code_FILE_yaml:
        code_file_yaml = yaml.safe_load(code_FILE_yaml)
except IOError:
    logger.error(
        "Could not load '%s' Odoo code configuration file.",
        CODE_YAML_FILE
        )
    exit(1)

# Convert code_file_yaml to waft_code_auto_tmp_yaml_dict
code_addons_yaml_original_entries_dict = dict()
code_addons_yaml_fixed_entries_dict = dict()
waft_code_auto_tmp_yaml_dict = dict()
for code_addons_yaml_original_repo in code_file_yaml:
    if type(code_file_yaml[code_addons_yaml_original_repo]) != dict:
        logger.warning(
            "In '%s' file:"
            "    Waft found unexpected '%' that should be a dictionary!"
            "    Waft ignored it.",
            CODE_YAML_FILE, code_addons_yaml_original_repo
        )
        continue
    if code_addons_yaml_original_repo in code_addons_yaml_original_entries_dict or \
    code_addons_yaml_original_repo in code_addons_yaml_fixed_entries_dict:
        logger.warning(
            "In '%s' file:"
            "    Waft found a duplicated addons repository configuration '%s'!"
            "    Waft ignored it.",
            CODE_YAML_FILE, code_addons_yaml_original_repo
        )
        continue
    addons_subpath_repo = re.sub("[^\.\-\_\/a-z0-9]", "", code_addons_yaml_original_repo.lower())
    if addons_subpath_repo in {'', '/'}:
        logger.warning(
            "In '%s' file:"
            "    Waft found unacceptable addons repository configuration '%s' string!"
            "    Waft ignored it.",
            CODE_YAML_FILE, code_addons_yaml_original_repo
        )
        continue
    subdirs_elements_lst = list()
    waft_main_auto_code_default_remote = str()
    if addons_subpath_repo in {'odoo', 'odoo/odoo', 'oca', 'ocb', 'oca/ocb'}:
        if 'odoo' in waft_code_auto_tmp_yaml_dict:
            logger.warning(
                "In '%s' file:"
                "    Waft found a duplicated 'odoo' addons repository configuration '%s'!"
                "    Waft ignored it.",
                CODE_YAML_FILE, code_addons_yaml_original_repo
            )
            continue
        else:
            if addons_subpath_repo in {'odoo', 'odoo/odoo'}:
                waft_main_auto_code_default_remote = 'https://github.com/odoo/odoo.git'
            else:
                waft_main_auto_code_default_remote = 'https://github.com/oca/ocb.git'
            addons_subpath_repo = 'odoo'
    else:
        for subdir_element in addons_subpath_repo.split('/'):
            if subdir_element != '':
                subdirs_elements_lst.append(subdir_element)
        if len(subdirs_elements_lst) != 1:
            addons_subpath_repo = '/'.join(subdirs_elements_lst[-2:])
        else:
            if addons_subpath_repo != 'odoo':
                addons_subpath_repo = os.path.join('oca', subdirs_elements_lst[0])
    if addons_subpath_repo in code_addons_yaml_fixed_entries_dict:
        logger.warning(
            "In '%s' file:"
            "    Waft found a duplicated addons repository configuration '%s'!"
            "    Waft ignored it.",
            CODE_YAML_FILE, code_addons_yaml_original_repo
        )
        continue
    if code_addons_yaml_original_repo != addons_subpath_repo:
        logger.info(
            "Waft took '%s' addons repository configuration name form '%S' file and convert it to '%s'.",
            code_addons_yaml_original_repo, CODE_YAML_FILE, addons_subpath_repo
        )
    waft_addons_auto_repo_tmp_dict = dict()
    code_addons_repo_yaml_original_dict = code_file_yaml[code_addons_yaml_original_repo]
    waft_addons_auto_repo_tmp_dict['code_addons_repo_yaml_original_dict'] = code_addons_repo_yaml_original_dict
    code_addons_yaml_original_entries_dict[code_addons_yaml_original_repo] = addons_subpath_repo
    code_addons_yaml_fixed_entries_dict[addons_subpath_repo] = code_addons_yaml_original_repo
    waft_addons_auto_repo_tmp_dict['code_addons_yaml_original_repo'] = code_addons_yaml_original_repo
    waft_addons_auto_repo_tmp_dict['addons_subpath_repo'] = addons_subpath_repo
    default_generate_merges = True
    waft_addons_auto_repo_tmp_dict['code_merges_yaml_original_lst'] = list()
    code_merges_yaml_original_lst = list()
    waft_merge_auto_remote = str()
    waft_merge_auto_tmp_dict = dict()
    waft_merges_auto_no_depth_tmp_lst = list()
    if 'merges' in code_addons_repo_yaml_original_dict:
        if type(code_addons_repo_yaml_original_dict['merges']) != list:
            logger.warning(
                "In '%s' file, '%s' dictionary:"
                "    Waft found unexpected '%' that should be a list!"
                "    Waft ignored it.",
                CODE_YAML_FILE, code_addons_yaml_original_repo, code_addons_repo_yaml_original_dict['merges']
            )
        else:
            code_merges_yaml_original_lst = code_addons_repo_yaml_original_dict['merges']
            if len(code_merges_yaml_original_lst) == 0:
                logger.warning(
                    "In '%s' file, '%s' dictionary:"
                    "    Waft found an empty 'merges:' list!"
                    "    Waft ignored it.",
                    CODE_YAML_FILE, code_addons_yaml_original_repo
                )
                code_merges_yaml_original_lst = list()
            else:
                default_generate_merges = False
                waft_addons_auto_repo_tmp_dict['code_merges_yaml_original_lst'] = code_merges_yaml_original_lst
    if addons_subpath_repo == 'odoo':
        waft_merge_auto_remote = waft_main_auto_code_default_remote
    else:
        waft_merge_auto_remote = "https://github.com/oca/{}.git".format(addons_subpath_repo)
    for code_merge_yaml_dict in code_merges_yaml_original_lst if not default_generate_merges else []:
        default_generate_remote = True
        code_merge_yaml_original_remote = str()
        waft_merge_auto_depth = str()
        if type(code_merge_yaml_dict) != dict:
            logger.warning(
                "In '%s' file, '%s' dictionary, '%s' list:"
                "    Waft found unexpected '%' that should be a dictionary!"
                "    Waft ignored it.",
                CODE_YAML_FILE, code_addons_yaml_original_repo,
                code_merges_yaml_original_lst, code_merge_yaml_dict
            )
            continue
        elif 'remote' not in code_merge_yaml_dict:
            logger.info(
                "In '%s' file, '%s' dictionary, '%s' list, '%s' dictionary:"
                "    Waft didn't find 'remote' key!"
                "    Waft will set it later.",
                CODE_YAML_FILE, code_addons_yaml_original_repo,
                code_merges_yaml_original_lst, code_merge_yaml_dict
            )
        elif type(code_merge_yaml_dict['remote']) != str:
            logger.warning(
                "In '%s' file, '%s' dictionary, '%s' list, '%s' dictionary:"
                "    Waft found unexpected 'remote: %s' that should be a string!"
                "    Waft will set it later.",
                CODE_YAML_FILE, code_addons_yaml_original_repo,
                code_merges_yaml_original_lst, code_merge_yaml_dict,
                code_merge_yaml_dict['remote']
            )
        else:
            code_merge_yaml_original_remote = code_merge_yaml_dict['remote']
            code_merge_yaml_fixed_remote = re.sub("[^\.\-\_\:\/a-z0-9]", "", code_merge_yaml_original_remote.lower())
            if code_merge_yaml_fixed_remote == '':
                logger.warning(
                    "In '%s' file, '%s' dictionary, '%s' list, '%s' dictionary:"
                    "    Waft found 'remote' key with an empty value!"
                    "    Waft will set it later.",
                    CODE_YAML_FILE, code_addons_yaml_original_repo,
                    code_merges_yaml_original_lst, code_merge_yaml_dict
                )
            else:
                default_generate_remote = False
                waft_merge_auto_remote = code_merge_yaml_fixed_remote
                if code_merge_yaml_original_remote != waft_merge_auto_remote:
                    logger.info(
                        "In '%s' file, '%s' dictionary, '%s' list, '%s' dictionary:"
                        "    Waft took 'remote: %s' and convert it to 'remote: %s'.",
                        CODE_YAML_FILE, code_addons_yaml_original_repo,
                        code_merges_yaml_original_lst, code_merge_yaml_dict,
                        code_merge_yaml_original_remote, waft_merge_auto_remote
                    )
                else:
                    logger.info(
                        "In '%s' file, '%s' dictionary, '%s' list, '%s' dictionary:"
                        "    Waft set 'remote: %s'.",
                        CODE_YAML_FILE, code_addons_yaml_original_repo,
                        code_merges_yaml_original_lst, code_merge_yaml_dict,
                        waft_merge_auto_remote
                    )
        if 'refs' not in code_merge_yaml_dict:
            logger.info(
                "In '%s' file, '%s' dictionary, '%s' list, '%s' dictionary:"
                "    Waft didn't find 'refs' list!"
                "    Waft will set it later.",
                CODE_YAML_FILE, code_addons_yaml_original_repo,
                code_merges_yaml_original_lst, code_merge_yaml_dict
            )
        elif type(code_merge_yaml_dict['refs']) != list:
            logger.warning(
                "In '%s' file, '%s' dictionary, '%s' list, '%s' dictionary:"
                "    Waft found unexpected '%' that should be a list!"
                "    Waft ignored it.",
                CODE_YAML_FILE, code_addons_yaml_original_repo,
                code_merges_yaml_original_lst, code_merge_yaml_dict, code_merge_yaml_dict['refs']
            )
        elif len(code_merge_yaml_dict['refs']) == 0:
            logger.warning(
                "In '%s' file, '%s' dictionary, '%s' list, '%s' dictionary:"
                "    Waft found an empty 'refs:' list!"
                "    Waft ignored it.",
                CODE_YAML_FILE, code_addons_yaml_original_repo
            )
        else:
            for code_merge_yaml_ref in code_merge_yaml_dict['refs']:
                if type(code_merge_yaml_ref) != str:
                    logger.warning(
                        "In '%s' file, '%s' dictionary, '%s' list, '%s' dictionary:"
                        "    Waft found unexpected value that should be a string!"
                        "    Waft ignored it.",
                        CODE_YAML_FILE, code_addons_yaml_original_repo,
                        code_merges_yaml_original_lst, code_merge_yaml_dict
                    )
                    continue
                code_merge_yaml_original_ref = code_merge_yaml_ref
                for odoo_variable_version in {'"${ODOO_VERSION}"', '${ODOO_VERSION}', '"$ODOO_VERSION"', '$ODOO_VERSION'}:
                    code_merge_yaml_ref = code_merge_yaml_ref.replace(odoo_variable_version, ODOO_VERSION)
                code_merge_yaml_fixed_ref = re.sub("[^\.\-\_\ a-z0-9]", "", code_merge_yaml_ref.lower())
                waft_merge_auto_branch = str()
                waft_merge_auto_pin = str()
                if code_merge_yaml_fixed_ref == '':
                    logger.warning(
                        "In '%s' file, '%s' dictionary, '%s' list, '%s' dictionary:"
                        "    Waft found an empty value!"
                        "    Waft will set it later.",
                        CODE_YAML_FILE, code_addons_yaml_original_repo,
                        code_merges_yaml_original_lst, code_merge_yaml_dict, ODOO_VERSION
                    )
                else:
                    if code_merge_yaml_original_ref != code_merge_yaml_fixed_ref:
                        logger.info(
                            "In '%s' file, '%s' dictionary, '%s' list, '%s' dictionary:"
                            "    Waft took '%s' and convert it to '%s'.",
                            CODE_YAML_FILE, code_addons_yaml_original_repo,
                            code_merges_yaml_original_lst, code_merge_yaml_dict,
                            code_merge_yaml_original_ref, code_merge_yaml_fixed_ref
                        )
                    else:
                        logger.info(
                            "In '%s' file, '%s' dictionary, '%s' list, '%s' dictionary:"
                            "    Waft set '%s'.",
                            CODE_YAML_FILE, code_addons_yaml_original_repo,
                            code_merges_yaml_original_lst, code_merge_yaml_dict,
                        )
                    for ref_element in code_merge_yaml_fixed_ref.split(' '):
                        if ref_element == '':
                            continue
                        if waft_merge_auto_branch == '':
                            waft_merge_auto_branch = ref_element
                        else:
                            waft_merge_auto_pin = ref_element
                            break
                if waft_merge_auto_branch == '' and default_generate_remote:
                    continue
                elif waft_merge_auto_branch == '':
                    waft_merge_auto_branch = ODOO_VERSION
                waft_merge_auto_no_depth_tmp_dict = dict()
                waft_merge_auto_no_depth_tmp_dict['code_merge_yaml_original_remote'] = code_merge_yaml_original_remote
                waft_merge_auto_no_depth_tmp_dict['waft_merge_auto_remote'] = waft_merge_auto_remote
                waft_merge_auto_no_depth_tmp_dict['code_merge_yaml_original_ref'] = code_merge_yaml_original_ref
                waft_merge_auto_no_depth_tmp_dict['code_merge_yaml_fixed_ref'] = code_merge_yaml_fixed_ref
                waft_merge_auto_no_depth_tmp_dict['remote'] = waft_merge_auto_remote
                waft_merge_auto_no_depth_tmp_dict['branch'] = waft_merge_auto_branch
                waft_merge_auto_no_depth_tmp_dict['pin'] = waft_merge_auto_pin
                waft_merges_auto_no_depth_tmp_lst.append(waft_merge_auto_no_depth_tmp_dict)
        code_merge_yaml_original_depth = int()
        if 'depth' not in code_merge_yaml_dict:
            waft_merge_auto_depth = 0
            logger.warning(
                "In '%s' file, '%s' dictionary, '%s' list, '%s' dictionary:"
                "    Waft didn't find 'depth' key!"
                "    Waft will set it later.",
                CODE_YAML_FILE, code_addons_yaml_original_repo,
                code_merges_yaml_original_lst, code_merge_yaml_dict
            )
        elif type(code_merge_yaml_dict['depth']) != str:
            waft_merge_auto_depth = 0
            logger.warning(
                "In '%s' file, '%s' dictionary, '%s' list, '%s' dictionary:"
                "    Waft found unexpected 'depth: %s' that should be a number!"
                "    Waft will set it later.",
                CODE_YAML_FILE, code_addons_yaml_original_repo,
                code_merges_yaml_original_lst, code_merge_yaml_dict,
                code_merge_yaml_dict['depth']
            )
        else:
            code_merge_yaml_original_depth = code_merge_yaml_dict['depth']
            code_merge_yaml_fixed_depth = re.sub("[^0-9]", "", code_merge_yaml_original_depth)
            code_merge_yaml_fixed_depth = int(code_merge_yaml_fixed_depth)
            if code_merge_yaml_fixed_depth == '':
                waft_merge_auto_depth = 0
                logger.warning(
                    "In '%s' file, '%s' dictionary, '%s' list, '%s' dictionary:"
                    "    Waft found 'depth' key with an empty value!"
                    "    Waft will set it later.",
                    CODE_YAML_FILE, code_addons_yaml_original_repo,
                    code_merges_yaml_original_lst, code_merge_yaml_dict
                )
            else:
                waft_merge_auto_depth = code_merge_yaml_fixed_depth
                if code_merge_yaml_original_depth != waft_merge_auto_depth:
                    logger.info(
                        "In '%s' file, '%s' dictionary, '%s' list, '%s' dictionary:"
                        "    Waft took 'depth: %s' and convert it to 'depth: %s'."
                        "    Waft will set depth later.",
                        CODE_YAML_FILE, code_addons_yaml_original_repo,
                        code_merges_yaml_original_lst, code_merge_yaml_dict,
                        code_merge_yaml_original_depth, waft_merge_auto_depth
                    )
        if waft_merge_auto_depth == 0:
            waft_merge_auto_depth = 77
            if len(waft_merges_auto_no_depth_tmp_lst) == 1:
                waft_merge_auto_no_depth_tmp_dict = waft_merges_auto_no_depth_tmp_lst[0]
                if waft_merge_auto_no_depth_tmp_dict['pin'] == '':
                    waft_merge_auto_depth = 1
                waft_merge_auto_no_depth_tmp_dict = dict()
        waft_merges_auto_tmp_lst = list()
        waft_merge_auto_tmp_dict = dict()
        for waft_merge_auto_no_depth_tmp_loop_dict in waft_merges_auto_no_depth_tmp_lst:
            waft_merge_auto_tmp_dict['code_merge_yaml_original_remote'] = waft_merge_auto_no_depth_tmp_loop_dict['code_merge_yaml_original_remote']
            waft_merge_auto_tmp_dict['waft_merge_auto_remote'] = waft_merge_auto_no_depth_tmp_loop_dict['waft_merge_auto_remote']
            waft_merge_auto_tmp_dict['code_merge_yaml_original_ref'] = waft_merge_auto_no_depth_tmp_loop_dict['code_merge_yaml_original_ref']
            waft_merge_auto_tmp_dict['code_merge_yaml_fixed_ref'] = waft_merge_auto_no_depth_tmp_loop_dict['code_merge_yaml_fixed_ref']
            waft_merge_auto_tmp_dict['code_merge_yaml_original_depth'] = code_merge_yaml_original_depth
            waft_merge_auto_tmp_dict['remote'] = waft_merge_auto_no_depth_tmp_loop_dict['remote']
            waft_merge_auto_tmp_dict['branch'] = waft_merge_auto_no_depth_tmp_loop_dict['branch']
            waft_merge_auto_tmp_dict['pin'] = waft_merge_auto_no_depth_tmp_loop_dict['pin']
            waft_merge_auto_tmp_dict['depth'] = waft_merge_auto_depth
            waft_merges_auto_tmp_lst.append(waft_merge_auto_tmp_dict)
