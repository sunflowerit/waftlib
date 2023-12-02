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
ODOO_WORK_DIRECTORY = os.path.realpath(os.path.join(SCRIPT_PATH, "../../../../.."))
os.environ['ODOO_WORK_DIRECTORY'] = ODOO_WORK_DIRECTORY
ODOO_CONFIG_DIRECTORY = os.path.join(ODOO_WORK_DIRECTORY, "config")
os.environ['ODOO_CONFIG_DIRECTORY'] = ODOO_CONFIG_DIRECTORY
load_dotenv(os.path.join(ODOO_CONFIG_DIRECTORY, "env-default"))
load_dotenv(os.path.join(ODOO_CONFIG_DIRECTORY, "env-shared"), override=True)
load_dotenv(os.path.join(ODOO_WORK_DIRECTORY, ".env-secret"), override=True)

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

CODE_ODOO_DIRECTORY = os.path.join(ODOO_WORK_DIRECTORY, "odoo-code")
CODE_ODOO_YAML_FILE = os.path.join(ODOO_CONFIG_DIRECTORY, "odoo-code.yaml")
ODOO_MAIN_CODE_PATH = os.path.join(ODOO_WORK_DIRECTORY, "odoo-code/odoo")
IGNORE_DIRECTORY = os.path.join(ODOO_WORK_DIRECTORY, ".ignore")
ODOO_AUTO_DIRECTORY = os.path.join(IGNORE_DIRECTORY, "auto")
ODOO_ADDONS_AUTO_DIRECTORY = os.path.join(ODOO_WORK_DIRECTORY, "addons")

# Check if CODE_ODOO_YAML_FILE exist.
if not os.path.exists(CODE_ODOO_YAML_FILE):
    logger.error(
        "Could not find '%s' Odoo code configuration file.",
        CODE_ODOO_YAML_FILE
        )
    exit(1)

# Load CODE_ODOO_YAML_FILE yaml file as code_odoo_yaml_file dictionary.
try:
    with open(CODE_ODOO_YAML_FILE) as code_ODOO_YAML_file:
        code_odoo_yaml_file = yaml.safe_load(code_ODOO_YAML_file)
except IOError:
    logger.error(
        "Could not load '%s' Odoo code configuration file.",
        CODE_ODOO_YAML_FILE
        )
    exit(1)

# Convert code_odoo_yaml_file to waft_auto_yaml_tmp_dic
code_odoo_yaml_entries_list = []
waft_auto_yaml_tmp_dic = dict()
for code_odoo_yaml_addons_repo_sub_path in code_odoo_yaml_file:
    addons_repo_dic = code_odoo_yaml_file[code_odoo_yaml_addons_repo_sub_path]
    if code_odoo_yaml_addons_repo_sub_path in code_odoo_yaml_entries_list:
        logger.warning(
            "In '%s' file:"
            "    Waft found a duplicated addons repository configuration '%s'!"
            "    Waft ignored it.",
            CODE_ODOO_YAML_FILE, code_odoo_yaml_addons_repo_sub_path
        )
        continue
    addons_repo_sub_path = re.sub("[^\.\-\_\/a-z0-9]", "", code_odoo_yaml_addons_repo_sub_path.lower())
    if addons_repo_sub_path in {'', '/'}:
        logger.warning(
            "In '%s' file:"
            "    Waft found unacceptable addons repository configuration '%s' string!"
            "    Waft ignored it.",
            CODE_ODOO_YAML_FILE, code_odoo_yaml_addons_repo_sub_path
        )
        continue
    subdirectories_elements_list = []
    if addons_repo_sub_path not in {'enterprise', 'private', 'odoo', 'odoo/odoo', 'oca', 'ocb', 'oca/ocb'}:
        for subdirectory_element in addons_repo_sub_path.split('/'):
            if subdirectory_element != '':
                subdirectories_elements_list.append(subdirectory_element)
        addons_repo_sub_path = '/'.join(subdirectories_elements_list[-2:])
    if addons_repo_sub_path in {'enterprise', 'private'}:
        continue
    if addons_repo_sub_path in {'odoo', 'odoo/odoo', 'oca', 'ocb', 'oca/ocb'} and \
    'odoo' in waft_auto_yaml_tmp_dic:
        logger.warning(
            "In '%s' file:"
            "    Waft found a duplicated 'odoo' addons repository configuration '%s'!"
            "    Waft ignored it.",
            CODE_ODOO_YAML_FILE, code_odoo_yaml_addons_repo_sub_path
        )
        continue
    if addons_repo_sub_path not in {'odoo', 'oca', 'ocb'}:
        if len(subdirectories_elements_list) == 1:
            addons_repo_sub_path = os.path.join('oca', subdirectories_elements_list[0])
    if addons_repo_sub_path in code_odoo_yaml_entries_list:
        logger.warning(
            "In '%s' file:"
            "    Waft found a duplicated addons repository configuration '%s'!"
            "    Waft ignored it.",
            CODE_ODOO_YAML_FILE, code_odoo_yaml_addons_repo_sub_path
        )
        continue
    waft_auto_main_code_remotes_dic = dict()
    if addons_repo_sub_path in {'odoo', 'odoo/odoo'}:
        waft_auto_main_code_remotes_dic = {'origin': 'https://github.com/odoo/odoo.git'}
        addons_repo_sub_path = 'odoo'
    if addons_repo_sub_path in {'oca', 'ocb', 'oca/ocb'}:
        waft_auto_main_code_remotes_dic = {'origin': 'https://github.com/oca/ocb.git'}
        addons_repo_sub_path = 'odoo'
    if code_odoo_yaml_addons_repo_sub_path != addons_repo_sub_path:
        logger.info(
            "Waft took '%s' addons repository configuration name form '%S' file and convert it to '%s'.",
            code_odoo_yaml_addons_repo_sub_path, CODE_ODOO_YAML_FILE, addons_repo_sub_path
        )
    code_odoo_yaml_entries_list.append(code_odoo_yaml_addons_repo_sub_path)
    waft_auto_remotes_dic = dict()
    default_merges_generate = False
    default_remotes_generate = False
    waft_auto_merges_dic = dict()
    waft_auto_merges_list = []
    if 'merges' in addons_repo_dic:
        default_merges_generate = False
        code_odoo_yaml_merges_list = code_odoo_yaml_file[addons_repo_sub_path].get('merges')
        if type(code_odoo_yaml_merges_list) != list:
            default_merges_generate = True
            logger.warning(
                "In '%s' file, '%s' dictionary:"
                "    Waft found unexpected '%' that should be a list!"
                "    Waft ignored it.",
                CODE_ODOO_YAML_FILE, code_odoo_yaml_addons_repo_sub_path, code_odoo_yaml_merges_list
                )
        else:
            for code_odoo_yaml_merge_dic in code_odoo_yaml_merges_list:
                waft_auto_merge_dic = dict()
                waft_auto_merge_remote = ''
                waft_auto_merge_ref = ''
                waft_auto_merge_depth = ''
                if type(code_odoo_yaml_merge_dic) != dict:
                    logger.warning(
                        "In '%s' file, '%s' dictionary, '%s' list:"
                        "    Waft found unexpected '%' that should be a dictionary!"
                        "    Waft ignored it.",
                        CODE_ODOO_YAML_FILE, code_odoo_yaml_addons_repo_sub_path,
                        code_odoo_yaml_merges_list, code_odoo_yaml_merge_dic,
                    )
                    continue
                elif 'remote' not in code_odoo_yaml_merge_dic:
                    waft_auto_merge_remote = 'origin'
                    logger.info(
                        "In '%s' file, '%s' dictionary, '%s' list, '%s' dictionary:"
                        "    Waft didn't find 'remote' key!"
                        "    Waft set it to be 'remote: origin'.",
                        CODE_ODOO_YAML_FILE, code_odoo_yaml_addons_repo_sub_path,
                        code_odoo_yaml_merges_list, code_odoo_yaml_merge_dic
                    )
                elif type(code_odoo_yaml_merge_dic['remote']) != str:
                    waft_auto_merge_remote = 'origin'
                    logger.warning(
                        "In '%s' file, '%s' dictionary, '%s' list, '%s' dictionary:"
                        "    Waft found unexpected 'remote: %s' that should be a string!"
                        "    Waft reset it to be 'remote: origin'.",
                        CODE_ODOO_YAML_FILE, code_odoo_yaml_addons_repo_sub_path,
                        code_odoo_yaml_merges_list, code_odoo_yaml_merge_dic,
                        code_odoo_yaml_merge_dic['remote']
                    )
                else:
                    waft_merge_original_remote = code_odoo_yaml_merge_dic['remote']
                    waft_merge_fixed_original_remote = re.sub("[^\.\-\_a-z0-9]", "", waft_merge_original_remote.lower())
                    if waft_merge_fixed_original_remote == '':
                        waft_auto_merge_remote = 'origin'
                        logger.warning(
                            "In '%s' file, '%s' dictionary, '%s' list, '%s' dictionary:"
                            "    Waft found 'remote' key with an empty value!"
                            "    Waft set it to be 'remote: origin'.",
                            CODE_ODOO_YAML_FILE, code_odoo_yaml_addons_repo_sub_path,
                            code_odoo_yaml_merges_list, code_odoo_yaml_merge_dic
                        )
                    else:
                        waft_auto_merge_remote = waft_merge_fixed_original_remote
                        if waft_merge_original_remote != waft_auto_merge_remote:
                            logger.info(
                                "In '%s' file, '%s' dictionary, '%s' list, '%s' dictionary:"
                                "    Waft took 'remote: %s' and convert it to 'remote: %s'.",
                                CODE_ODOO_YAML_FILE, code_odoo_yaml_addons_repo_sub_path,
                                code_odoo_yaml_merges_list, code_odoo_yaml_merge_dic,
                                waft_merge_original_remote, waft_auto_merge_remote
                            )
                        else:
                            logger.info(
                                "In '%s' file, '%s' dictionary, '%s' list, '%s' dictionary:"
                                "    Waft set 'remote: %s'.",
                                CODE_ODOO_YAML_FILE, code_odoo_yaml_addons_repo_sub_path,
                                code_odoo_yaml_merges_list, code_odoo_yaml_merge_dic,
                                waft_auto_merge_remote
                            )
                if 'ref' not in code_odoo_yaml_merge_dic:
                    waft_auto_merge_ref = ODOO_VERSION
                    logger.info(
                        "In '%s' file, '%s' dictionary, '%s' list, '%s' dictionary:"
                        "    Waft didn't find 'ref' key!"
                        "    Waft set it to be 'ref: %s'.",
                        CODE_ODOO_YAML_FILE, code_odoo_yaml_addons_repo_sub_path,
                        code_odoo_yaml_merges_list, code_odoo_yaml_merge_dic, ODOO_VERSION
                    )
                elif type(code_odoo_yaml_merge_dic['ref']) != str:
                    waft_auto_merge_ref = ODOO_VERSION
                    logger.warning(
                        "In '%s' file, '%s' dictionary, '%s' list, '%s' dictionary:"
                        "    Waft found unexpected 'ref: %s' that should be a string!"
                        "    Waft reset it to be 'remote: origin'.",
                        CODE_ODOO_YAML_FILE, code_odoo_yaml_addons_repo_sub_path,
                        code_odoo_yaml_merges_list, code_odoo_yaml_merge_dic,
                        code_odoo_yaml_merge_dic['ref']
                    )
                elif code_odoo_yaml_merge_dic['ref'] in \
                {'', 'ODOO_VERSION', '$ODOO_VERSION', '"$ODOO_VERSION"', '${ODOO_VERSION}', '"${ODOO_VERSION}"'}:
                    waft_auto_merge_ref = ODOO_VERSION
                else:
                    waft_merge_original_ref = code_odoo_yaml_merge_dic['ref']
                    waft_merge_fixed_original_ref = re.sub("[^\.\-\_\/a-z0-9]", "", waft_merge_original_ref.lower())
                    if waft_merge_fixed_original_ref == '' :
                        waft_auto_merge_ref = ODOO_VERSION
                        logger.warning(
                            "In '%s' file, '%s' dictionary, '%s' list, '%s' dictionary:"
                            "    Waft found 'ref' key with an empty value!"
                            "    Waft set it to be 'ref: %s'.",
                            CODE_ODOO_YAML_FILE, code_odoo_yaml_addons_repo_sub_path,
                            code_odoo_yaml_merges_list, code_odoo_yaml_merge_dic, ODOO_VERSION
                        )
                    else:
                        waft_auto_merge_ref = waft_merge_fixed_original_ref
                        if waft_merge_original_ref != waft_auto_merge_ref:
                            logger.info(
                                "In '%s' file, '%s' dictionary, '%s' list, '%s' dictionary:"
                                "    Waft took 'ref: %s' and convert it to 'ref: %s'.",
                                CODE_ODOO_YAML_FILE, code_odoo_yaml_addons_repo_sub_path,
                                code_odoo_yaml_merges_list, code_odoo_yaml_merge_dic,
                                waft_merge_original_ref, waft_auto_merge_ref
                            )
                        else:
                            logger.info(
                                "In '%s' file, '%s' dictionary, '%s' list, '%s' dictionary:"
                                "    Waft set 'ref: %s'.",
                                CODE_ODOO_YAML_FILE, code_odoo_yaml_addons_repo_sub_path,
                                code_odoo_yaml_merges_list, code_odoo_yaml_merge_dic,
                                waft_auto_merge_ref
                            )
                if 'depth' not in code_odoo_yaml_merge_dic:
                    waft_auto_merge_depth = 0
                    logger.warning(
                        "In '%s' file, '%s' dictionary, '%s' list, '%s' dictionary:"
                        "    Waft didn't find 'depth' key!"
                        "    Waft will set it later.",
                        CODE_ODOO_YAML_FILE, code_odoo_yaml_addons_repo_sub_path,
                        code_odoo_yaml_merges_list, code_odoo_yaml_merge_dic
                    )
                elif type(code_odoo_yaml_merge_dic['depth']) != str:
                    waft_auto_merge_depth = 0
                    logger.warning(
                        "In '%s' file, '%s' dictionary, '%s' list, '%s' dictionary:"
                        "    Waft found unexpected 'depth: %s' that should be a number!"
                        "    Waft will set it later.",
                        CODE_ODOO_YAML_FILE, code_odoo_yaml_addons_repo_sub_path,
                        code_odoo_yaml_merges_list, code_odoo_yaml_merge_dic,
                        code_odoo_yaml_merge_dic['depth']
                    )
                else:
                    waft_merge_original_depth = code_odoo_yaml_merge_dic['depth']
                    waft_merge_fixed_original_depth = re.sub("[^0-9]", "", waft_merge_original_depth)
                    waft_merge_fixed_original_depth = int(waft_merge_fixed_original_depth)
                    if waft_merge_fixed_original_depth == '' :
                        waft_auto_merge_depth = 0
                        logger.warning(
                            "In '%s' file, '%s' dictionary, '%s' list, '%s' dictionary:"
                            "    Waft found 'depth' key with an empty value!"
                            "    Waft will set it later.",
                            CODE_ODOO_YAML_FILE, code_odoo_yaml_addons_repo_sub_path,
                            code_odoo_yaml_merges_list, code_odoo_yaml_merge_dic
                        )
                    else:
                        waft_auto_merge_depth = waft_merge_fixed_original_depth
                        if waft_merge_original_depth != waft_auto_merge_depth:
                            logger.info(
                                "In '%s' file, '%s' dictionary, '%s' list, '%s' dictionary:"
                                "    Waft took 'depth: %s' and convert it to 'depth: %s'."
                                "    Waft will set depth later.",
                                CODE_ODOO_YAML_FILE, code_odoo_yaml_addons_repo_sub_path,
                                code_odoo_yaml_merges_list, code_odoo_yaml_merge_dic,
                                waft_merge_original_depth, waft_auto_merge_depth
                            )
                waft_auto_merge_key = "{}|{}".format(waft_auto_merge_remote, waft_auto_merge_ref)
                waft_auto_merge_dic['remote'] = waft_auto_merge_remote
                waft_auto_merge_dic['ref'] = waft_auto_merge_ref
                if waft_auto_merge_key in waft_auto_merges_dic:
                    if waft_auto_merge_depth == waft_auto_merges_dic[waft_auto_merge_key][depth]:
                        logger.info(
                            "In '%s' file, '%s' dictionary, '%s' list:"
                            "    Waft found a duplicate dictionary '%s'!"
                            "    Waft ignored the second one!"
                            "    Waft set 'depth: %s'.",
                            CODE_ODOO_YAML_FILE, code_odoo_yaml_addons_repo_sub_path,
                            code_odoo_yaml_merges_list, waft_auto_merges_dic[waft_auto_merge_key],
                            waft_auto_merge_depth
                        )
                    elif waft_auto_merge_depth > waft_auto_merges_dic[waft_auto_merge_key][depth]:
                        waft_auto_merge_dic['depth'] = waft_auto_merge_depth
                        logger.info(
                            "In '%s' file, '%s' dictionary, '%s' list:"
                            "    Waft found a duplicate dictionary '%s' with different depths:!"
                            "    Waft ignored '%s' and chose '%s' depth!"
                            "    Waft set 'depth: %s'.",
                            CODE_ODOO_YAML_FILE, code_odoo_yaml_addons_repo_sub_path,
                            code_odoo_yaml_merges_list, waft_auto_merge_dic,
                            waft_auto_merges_dic[waft_auto_merge_key][depth], waft_auto_merge_depth,
                            waft_auto_merge_depth
                        )
                        waft_auto_merges_dic[waft_auto_merge_key] = waft_auto_merge_dic
                    else:
                        waft_auto_merge_dic['depth'] = waft_auto_merges_dic[waft_auto_merge_key][depth]
                        logger.info(
                            "In '%s' file, '%s' dictionary, '%s' list:"
                            "    Waft found a duplicate dictionary '%s' with different depths:!"
                            "    Waft ignored '%s' and chose '%s' depth!"
                            "    Waft set 'depth: %s'.",
                            CODE_ODOO_YAML_FILE, code_odoo_yaml_addons_repo_sub_path,
                            code_odoo_yaml_merges_list, waft_auto_merge_dic,
                            waft_auto_merge_depth, waft_auto_merges_dic[waft_auto_merge_key][depth],
                            waft_auto_merges_dic[waft_auto_merge_key][depth]
                        )
                        waft_auto_merges_dic[waft_auto_merge_key] = waft_auto_merge_dic
                else:
                    waft_auto_merge_dic['depth'] = waft_auto_merge_depth
                    logger.info(
                        "In '%s' file, '%s' dictionary, '%s' list, '%s' dictionary:"
                        "    Waft set 'depth: %s'.",
                        CODE_ODOO_YAML_FILE, code_odoo_yaml_addons_repo_sub_path,
                        code_odoo_yaml_merges_list, code_odoo_yaml_merge_dic,
                        waft_auto_merge_depth
                    )
                    waft_auto_merges_dic[waft_auto_merge_key] = waft_auto_merge_dic
            if len(waft_auto_merges_dic) == 0:
                default_merges_generate = True
    else:
        default_merges_generate = True
