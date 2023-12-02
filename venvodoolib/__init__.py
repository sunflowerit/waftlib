#!/usr/bin/env python
# Version: v.23.08.03
# -*- coding: utf-8 -*-

from dotenv import load_dotenv
from glob import glob
from importlib import reload
import logging
import os
from subprocess import check_output, check_call
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

if not os.path.exists(CODE_ODOO_YAML_FILE):
    logger.error(
        "Could not find '%s' Odoo code configuration file.",
        CODE_ODOO_YAML_FILE
        )
    exit(1)

try:
    with open(CODE_ODOO_YAML_FILE) as code_ODOO_YAML_file:
        code_odoo_yaml_file = yaml.safe_load(code_ODOO_YAML_file)
except IOError:
    logger.error(
        "Could not load '%s' Odoo code configuration file.",
        CODE_ODOO_YAML_FILE
        )
    exit(1)

waft_auto_yaml_tmp_dic = dict()
for addons_repo_sub_path in code_odoo_yaml_file:
    if addons_repo_sub_path in {'enterprise', 'private'}:
        continue
    addons_repo_dic = code_odoo_yaml_file[addons_repo_sub_path]
    if 'remotes' not in addons_repo_dic:
        logger.warning(
            "Waft will ignore '%s' dictionary in '%s' file because it does not have 'remotes' dictionary!",
            addons_repo_sub_path, CODE_ODOO_YAML_FILE
            )
        continue
    code_odoo_yaml_remotes_dic = code_odoo_yaml_file[addons_repo_sub_path].get('remotes')
    waft_auto_remotes_tmp_dic = dict()
    if type(code_odoo_yaml_remotes_dic) != dict:
        logger.warning(
            "Waft will ignore '%s' dictionary in '%s' file because 'remotes: %s' is not a dictionary!",
            addons_repo_sub_path, CODE_ODOO_YAML_FILE, code_odoo_yaml_remotes_dic
            )
        continue
    default_merges_generated = False
    waft_auto_merges_list = []
    if 'merges' not in addons_repo_dic:
        for code_odoo_yaml_remote_key in code_odoo_yaml_remotes_dic:
            default_merges_generated = True
            waft_auto_merge_dic = dict()
            waft_auto_merge_dic['remote'] = code_odoo_yaml_remote_key
            waft_auto_merge_dic['ref'] = ODOO_VERSION
            waft_auto_merge_dic['depth'] = 1
            waft_auto_merges_list = [waft_auto_merge_dic]
            code_odoo_yaml_merges_list = []
            logger.warning(
                "'merges' dictionaries list does not exist in '%s' dictionary from '%s' Waft will generate it to be 'merges: %s'!",
                addons_repo_sub_path, CODE_ODOO_YAML_FILE, waft_auto_merges_list
                )
            break
    if not default_merges_generated:
        code_odoo_yaml_merges_list = code_odoo_yaml_file[addons_repo_sub_path].get('merges')
        if type(code_odoo_yaml_merges_list) != list:
            logger.warning(
                "Waft will ignore '%s' dictionary in '%s' file because 'merges: %s' is not a list!",
                addons_repo_sub_path, CODE_ODOO_YAML_FILE, code_odoo_yaml_merges_list
                )
            continue
        for code_odoo_yaml_remote_key in code_odoo_yaml_remotes_dic:
            for code_odoo_yaml_merge_dic in code_odoo_yaml_merges_list:
                if 'remote' in code_odoo_yaml_merge_dic \
                and code_odoo_yaml_merge_dic['remote'] == code_odoo_yaml_remote_key:
                    waft_auto_remotes_tmp_dic[code_odoo_yaml_remote_key] = \
                    code_odoo_yaml_remotes_dic[code_odoo_yaml_remote_key]
        if len(waft_auto_remotes_tmp_dic) == 0:
            logger.warning(
                "Waft will ignore '%s' dictionary in '%s' file because 'remotes: %s' dictionary is not correct!",
                addons_repo_sub_path, CODE_ODOO_YAML_FILE, code_odoo_yaml_remotes_dic
                )
            continue
        for code_odoo_yaml_merge_dic in code_odoo_yaml_merges_list:
            waft_auto_merge_dic = dict()
            waft_auto_merge_remote = ''
            waft_auto_merge_ref = ''
            if type(code_odoo_yaml_merge_dic) != dict:
                logger.warning(
                    "In '%s' dictionary in '%s' file, Waft will ignore '%s' in 'merges: %s' because it is not a dictionary!",
                    addons_repo_sub_path, CODE_ODOO_YAML_FILE, code_odoo_yaml_merge_dic, code_odoo_yaml_remotes_dic
                    )
                continue
            elif 'remote' not in code_odoo_yaml_merge_dic:
                logger.warning(
                    "Waft will ignore 'merges: %s' dictionary from '%s' dictionary in '%s' file "
                    "because 'remote:' key is not exist in 'remotes: %s'!",
                    code_odoo_yaml_merge_dic, addons_repo_sub_path, CODE_ODOO_YAML_FILE, waft_auto_remotes_tmp_dic
                    )
                continue
            elif code_odoo_yaml_merge_dic['remote'] == '':
                logger.warning(
                    "Waft will ignore 'merges: %s' dictionary from '%s' dictionary in '%s' file because 'remote:' key is empty!",
                    code_odoo_yaml_merge_dic, addons_repo_sub_path, CODE_ODOO_YAML_FILE
                    )
                continue
            elif code_odoo_yaml_merge_dic['remote'] not in waft_auto_remotes_tmp_dic:
                logger.warning(
                    "Waft will ignore 'merges: %s' dictionary from '%s' dictionary in '%s' file "
                    "because 'remote: %s' key is not in 'remotes: %s'!",
                    code_odoo_yaml_merge_dic, addons_repo_sub_path, CODE_ODOO_YAML_FILE,
                    code_odoo_yaml_merge_dic['remote'], waft_auto_remotes_tmp_dic
                    )
                continue
            elif type(code_odoo_yaml_merge_dic['remote']) != str:
                logger.warning(
                    "Waft will ignore 'merges: %s' dictionary from '%s' dictionary in '%s' file "
                    "because 'remote: %s' is not is not a string!",
                    code_odoo_yaml_merge_dic, addons_repo_sub_path, CODE_ODOO_YAML_FILE, waft_auto_merge_remote
                    )
                continue
            else:
                waft_auto_merge_remote = code_odoo_yaml_merge_dic['remote']
            if 'ref' not in code_odoo_yaml_merge_dic:
                waft_auto_merge_ref = ODOO_VERSION
            elif code_odoo_yaml_merge_dic['ref'] in {'', 'ODOO_VERSION', '$ODOO_VERSION', '"$ODOO_VERSION"',
            '${ODOO_VERSION}', '"${ODOO_VERSION}"'}:
                waft_auto_merge_ref = ODOO_VERSION
            else:
                waft_auto_merge_ref = code_odoo_yaml_merge_dic['ref']
            if type(waft_auto_merge_ref) != str:
                logger.warning(
                    "Waft will ignore 'merges: %s' dictionary from '%s' dictionary in '%s' file "
                    "because 'ref: %s' is not is not a string!",
                    code_odoo_yaml_merge_dic, addons_repo_sub_path, CODE_ODOO_YAML_FILE, waft_auto_merge_ref
                    )
                continue
            if 'depth' not in code_odoo_yaml_merge_dic:
                waft_auto_merge_depth = 1
            else:
                waft_auto_merge_depth = code_odoo_yaml_merge_dic['depth']
            if type(waft_auto_merge_depth) != int:
                logger.warning(
                    "Waft will ignore 'merges: %s' dictionary from '%s' dictionary in '%s' file "
                    "because 'depth: %s' is not is not a string!",
                    code_odoo_yaml_merge_dic, addons_repo_sub_path, CODE_ODOO_YAML_FILE, waft_auto_merge_depth
                    )
                continue
            waft_auto_merge_dic['remote'] = waft_auto_merge_remote
            waft_auto_merge_dic['ref'] = waft_auto_merge_ref
            waft_auto_merge_dic['depth'] = waft_auto_merge_depth
            waft_auto_merges_list.append(waft_auto_merge_dic)
        if len(waft_auto_merges_list) == 0:
            for code_odoo_yaml_remote_key in code_odoo_yaml_remotes_dic:
                default_merges_generated = True
                waft_auto_merge_dic = dict()
                waft_auto_merge_dic['remote'] = code_odoo_yaml_remote_key
                waft_auto_merge_dic['ref'] = ODOO_VERSION
                waft_auto_merge_dic['depth'] = 1
                waft_auto_merges_list = [waft_auto_merge_dic]
                code_odoo_yaml_merges_list = []
                logger.warning(
                    "'merges' dictionaries list does not exist in '%s' dictionary from '%s' Waft will generate it to be 'merges: %s'!",
                    addons_repo_sub_path, CODE_ODOO_YAML_FILE, waft_auto_merges_list
                    )
                break
        if len(waft_auto_merges_list) > 1:
            waft_auto_merges_tmp_list = []
            for waft_auto_merge_tmp_dic in waft_auto_merges_list:
                if waft_auto_merge_tmp_dic['depth'] == 1:
                    waft_auto_merge_tmp_dic['depth'] = WAFT_DEPTH_MERGE
                waft_auto_merges_tmp_list.append(waft_auto_merge_tmp_dic)
            waft_auto_merges_list = waft_auto_merges_tmp_list
    waft_auto_remotes_dic = dict()
    if default_merges_generated:
        for code_odoo_yaml_remote_key in code_odoo_yaml_remotes_dic:
            waft_auto_remotes_dic[code_odoo_yaml_remote_key] = code_odoo_yaml_remotes_dic[code_odoo_yaml_remote_key]
            break
    else:
        if len(waft_auto_remotes_tmp_dic) > 1:
            for waft_auto_remote_key in waft_auto_remotes_tmp_dic:
                for waft_auto_merge_tmp_dic in waft_auto_merges_list:
                    if waft_auto_merge_tmp_dic['remote'] == waft_auto_remote_key:
                        waft_auto_remotes_dic[waft_auto_remote_key] = waft_auto_remotes_tmp_dic[waft_auto_remote_key]
    waft_auto_target_default_value = ''
    for waft_auto_merge_tmp_dic in waft_auto_merges_list:
        waft_auto_target_default_value = "{} {}".format(
            waft_auto_merge_tmp_dic['remote'], waft_auto_merge_tmp_dic['ref']
            )
        break
    code_odoo_yaml_target_value = ''
    waft_auto_target_value = ''
    waft_auto_default_target = False
    if 'target' not in addons_repo_dic:
        waft_auto_default_target = True
        waft_auto_target_value = waft_auto_target_default_value
        logger.warning(
            "'target' string does not exist in '%s' dictionary from '%s' waft will generate it to be 'target: %s'!",
            addons_repo_sub_path, CODE_ODOO_YAML_FILE, waft_auto_target_default_value
            )
    if not waft_auto_default_target:
        code_odoo_yaml_target_value = code_odoo_yaml_file[addons_repo_sub_path].get('target')
        if type(code_odoo_yaml_target_value) != str:
            code_odoo_yaml_target_value = ''
            waft_auto_target_value = waft_auto_target_default_value
            logger.warning(
                "'target' in '%s' dictionary from '%s' is not a string, Waft will generate it to be 'target: %s'!",
                addons_repo_sub_path, CODE_ODOO_YAML_FILE, waft_auto_target_default_value
                )
        code_odoo_yaml_target_list = code_odoo_yaml_target_value.split()
        if len(code_odoo_yaml_target_list) != 2:
            code_odoo_yaml_target_value = ''
            waft_auto_target_value = waft_auto_target_default_value
            logger.warning(
                "'target' in '%s' dictionary from '%s' is not correct, Waft will generate it to be 'target: %s'!",
                addons_repo_sub_path, CODE_ODOO_YAML_FILE, waft_auto_target_default_value
                )
        if code_odoo_yaml_target_list[0] not in waft_auto_remotes_tmp_dic:
            code_odoo_yaml_target_value = ''
            waft_auto_target_value = waft_auto_target_default_value
            logger.warning(
                "'target' in '%s' dictionary from '%s' is not in merges' remote list, Waft will generate it to be 'target: %s'!",
                addons_repo_sub_path, CODE_ODOO_YAML_FILE, waft_auto_target_default_value
                )
    waft_auto_repo_dic = dict()
    waft_auto_repo_dic['remotes'] = waft_auto_remotes_dic
    waft_auto_repo_dic['target'] = waft_auto_target_value
    waft_auto_repo_dic['merges'] = waft_auto_merges_list
    addons_repo_full_path = os.path.join(CODE_ODOO_DIRECTORY, addons_repo_sub_path)
    waft_auto_default_addons = False
    if 'addons' not in addons_repo_dic:
        waft_auto_default_addons = True
        logger.warning(
            "'addons' list does not exist in '%s' dictionary, so, all addons will be linked!",
            addons_repo_sub_path
            )
        waft_auto_repo_dic['addons'] = [os.path.join(addons_repo_full_path, '*')]
    if not waft_auto_default_addons:
        if type(addons_repo_dic['addons']) != list:
            logger.warning(
                "'addons: %s' is not a list in '%s' dictionary in '%s' file, so, all addons will be linked!",
                addons_repo_dic['addons'], addons_repo_sub_path, CODE_ODOO_YAML_FILE
                )
            waft_auto_repo_dic['addons'] = [os.path.join(addons_repo_full_path, '*')]
        else:
            waft_auto_repo_addons_list = []
            for addon_sub_path in addons_repo_dic['addons']:
                addon_full_path = os.path.join(addons_repo_full_path, addon_sub_path)
                waft_auto_repo_addons_list.append(addon_full_path)
            waft_auto_repo_dic['addons'] = waft_auto_repo_addons_list
    waft_auto_addons_default_except = False
    if 'addons_except' not in addons_repo_dic:
        waft_auto_addons_default_except = True
        logger.warning(
            "'addons_except' list does not exist in '%s' dictionary, so, addons_except will be nothing!",
            addons_repo_sub_path
            )
        waft_auto_repo_dic['addons_except'] = []
    if not waft_auto_addons_default_except:
        if type(addons_repo_dic['addons_except']) != list:
            logger.warning(
                "'addons_except: %s' is not a list, so, addons_except will be nothing!",
                addons_repo_dic['addons_except'], addons_repo_sub_path, CODE_ODOO_YAML_FILE
                )
            waft_auto_repo_dic['addons_except'] = []
        else:
            waft_auto_repo_addons_except_list = []
            for addon_except_sub_path in addons_repo_dic['addons_except']:
                addon_except_full_path = os.path.join(addons_repo_full_path, addon_except_sub_path)
                waft_auto_repo_addons_except_list.append(addon_except_full_path)
            waft_auto_repo_dic['addons_except'] = waft_auto_repo_addons_except_list
    waft_auto_yaml_tmp_dic[addons_repo_full_path] = waft_auto_repo_dic

waft_auto_yaml_dic = dict()
if ODOO_MAIN_CODE_PATH not in waft_auto_yaml_tmp_dic:
    waft_auto_repo_dic = dict()
    waft_auto_repo_dic['remotes'] = {'origin': 'https://github.com/odoo/odoo.git'}
    waft_auto_repo_dic['target'] = "origin {}".format(
        ODOO_VERSION
        )
    waft_auto_merge_dic = dict()
    waft_auto_merge_dic['remote'] = origin
    waft_auto_merge_dic['ref'] = ODOO_VERSION
    waft_auto_merges_list = [waft_auto_merge_dic]
    waft_auto_repo_dic['merges'] = waft_auto_merges_list
    waft_auto_repo_dic['addons'] = [os.path.join(ODOO_MAIN_CODE_PATH, '*')]
    waft_auto_repo_dic['addons_except'] = []
    waft_auto_yaml_dic[ODOO_MAIN_CODE_PATH] = waft_auto_repo_dic
for addons_repo_sub_path in {'enterprise', 'private'}:
    if addons_repo_sub_path in code_odoo_yaml_file:
        addons_repo_dic = code_odoo_yaml_file[addons_repo_sub_path]
        waft_auto_repo_dic = dict()
        waft_auto_repo_dic['remotes'] = dict()
        waft_auto_repo_dic['target'] = ''
        waft_auto_repo_dic['merges'] = []
        addons_repo_full_path = os.path.join(CODE_ODOO_DIRECTORY, addons_repo_sub_path)
        waft_auto_default_addons = False
        if 'addons' not in addons_repo_dic:
            waft_auto_default_addons = True
            logger.warning(
                "'addons' list does not exist in '%s' dictionary, so, all addons will be linked!",
                addons_repo_sub_path
                )
            waft_auto_repo_dic['addons'] = [os.path.join(addons_repo_full_path, '*')]
        if not waft_auto_default_addons:
            if type(addons_repo_dic['addons']) != list:
                logger.warning(
                    "'addons: %s' is not a list in '%s' dictionary in '%s' file, so, all addons will be linked!",
                    addons_repo_dic['addons'], addons_repo_sub_path, CODE_ODOO_YAML_FILE
                    )
                waft_auto_repo_dic['addons'] = [os.path.join(addons_repo_full_path, '*')]
            else:
                waft_auto_repo_addons_list = []
                for addon_sub_path in addons_repo_dic['addons']:
                    addon_full_path = os.path.join(addons_repo_full_path, addon_sub_path)
                    waft_auto_repo_addons_list.append(addon_full_path)
                waft_auto_repo_dic['addons'] = waft_auto_repo_addons_list
        waft_auto_addons_default_except = False
        if 'addons_except' not in addons_repo_dic:
            waft_auto_addons_default_except = True
            logger.warning(
                "'addons_except' list does not exist in '%s' dictionary, so, addons_except will be nothing!",
                addons_repo_sub_path
                )
            waft_auto_repo_dic['addons_except'] = []
        if not waft_auto_addons_default_except:
            if type(addons_repo_dic['addons_except']) != list:
                logger.warning(
                    "'addons_except: %s' is not a list, so, addons_except will be nothing!",
                    addons_repo_dic['addons_except'], addons_repo_sub_path, CODE_ODOO_YAML_FILE
                    )
                waft_auto_repo_dic['addons_except'] = []
            else:
                waft_auto_repo_addons_except_list = []
                for addon_except_sub_path in addons_repo_dic['addons_except']:
                    addon_except_full_path = os.path.join(addons_repo_full_path, addon_except_sub_path)
                    waft_auto_repo_addons_except_list.append(addon_except_full_path)
                waft_auto_repo_dic['addons_except'] = waft_auto_repo_addons_except_list
        waft_auto_yaml_dic[addons_repo_full_path] = waft_auto_repo_dic

for addons_repo_full_path in waft_auto_yaml_tmp_dic:
    waft_auto_yaml_dic[addons_repo_full_path] = waft_auto_yaml_tmp_dic[addons_repo_full_path]

addons_repo_sub_path = ''
addons_repo_full_path = ''
addons_enterprise_full_path = os.path.join(CODE_ODOO_DIRECTORY, 'enterprise')
addons_private_full_path = os.path.join(CODE_ODOO_DIRECTORY, 'private')
addons_repo_dic = dict()
waft_auto_repo_dic = dict()
code_odoo_yaml_remotes_dic = dict()
waft_auto_remotes_tmp_dic = dict()
waft_auto_remotes_dic = dict()
code_odoo_yaml_remote_key = ''
waft_auto_remote_key = ''
code_odoo_yaml_merges_list = []
waft_auto_merges_tmp_list = []
waft_auto_merges_list = []
code_odoo_yaml_merge_dic = dict()
waft_auto_merge_tmp_dic = dict()
waft_auto_merge_dic = dict()
default_merges_generated = False
waft_auto_merge_remote = ''
waft_auto_merge_ref = ''
waft_auto_merge_depth = 1
code_odoo_yaml_target_list = []
waft_auto_default_target = False
code_odoo_yaml_target_value = ''
waft_auto_target_value = ''
waft_auto_target_default_value = ''
waft_auto_default_addons = False
addon_sub_path = ''
addon_full_path = ''
addon_except_sub_path = ''
addon_except_full_path = ''
waft_auto_repo_addons_except_list = []
waft_auto_addons_default_except = False
waft_auto_repo_addons_list = []
