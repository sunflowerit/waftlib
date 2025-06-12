#!/usr/bin/env python3
import copy
import getopt
import io
import json
import logging
from math import floor
import os

try:
    import psycopg
except ImportError:
    import psycopg2 as psycopg
import yaml
import shutil
import subprocess
import sys
from tempfile import mkstemp
import time
from threading import Thread
import traceback
from urllib.request import urlopen
from queue import Queue, Empty


# Adjust this to the minimum supported target version by the enterprise script
# whenever Odoo decides to change it.
ENTERPRISE_MINIMUM_TARGET = "15.0"
HELP_TEXT = """
Parameters
===================

--database NAME
-d NAME     Specify a databasename that overrides the name from the
            configuration file.
--enterprise-enabled
-e          Enable the enterprise migration scripts as well.
--start-version VERSION
-f VERSION  Start migration from a database of this Odoo version. This could
            prevent pre-migration scripts from running.
--help
-h          Show this help message.
--open-upgrade-disabled
-o          Disable the open-upgrade builds and upgrades.
--production
-p          Run the migration for production purposes.
--restore
-s          Restore a database from the configured path.
-r          Rebuild all builds before running the migration.
--reset-progress VERSION[:openupgrade]
            Don't take into account the progress that is specified with this
            option and beyond. The migration will start from here if progress
            is beyond what is specified here.
            VERSION should be the Odoo version, such as "12.0" or "14.0".
            openupgrade is optional, but if provided, will only start 
--verbose
-v          Log debug messages.
--enterprise-dont-resume
            Don't resume the enterprise upgrade request when given the option.
"""
SCRIPT_PATH = os.path.abspath(os.path.dirname(__file__))
WAFT_DIR = os.path.realpath(os.path.join(SCRIPT_PATH, "../.."))
MIGRATION_PATH = WAFT_DIR + "/migration"

# Global variables
params = {}
progress = {}
db_version = None
enterprise_script_filepath = None


class CommandFailedException(Exception):
    def __init__(self, command, exit_code):
        self.command = command
        self.exit_code = exit_code

    def __str__(self):
        return "The following command failed with exit code %s: %s" % (
            str(self.exit_code),
            self.command,
        )


def available_enterprise_build_versions(start_version, minimum_target):
    return [
        version
        for version in available_build_versions(start_version)
        if version == start_version or float(version) - float(minimum_target) >= -0.01
    ]


def available_build_versions(start_version):
    global params
    end_version = floor(float(os.environ["ODOO_VERSION"]))
    return [str(x) + ".0" for x in range(floor(float(start_version)), end_version + 1)]


def check_modules_installed(modules):
    """Returns whether or not the given `modules` are installed in the
    current database.
    """
    with psycopg.connect("dbname=" + os.environ["PGDATABASE"]) as conn:
        with conn.cursor() as cur:
            for module in modules:
                cur.execute(
                    "SELECT * FROM ir_module_module WHERE "
                    "state <> 'uninstalled' AND name = %s",
                    [module],
                )
                if not cur.rowcount:
                    return False
    return True


def check_script_support(filename, version):
    comment_prefix = "--" if filename.endswith(".sql") else "#"
    file = open(filename, "r")

    for line in file:
        stripped_line = line.strip()
        # Only parse comments in the top of the file
        if not stripped_line.startswith(comment_prefix):
            break

        comment = stripped_line[len(comment_prefix) :].strip()
        if comment.startswith("X-Supports:"):
            versions = [x.strip() for x in comment[11:].split()]
            if not version in versions:
                return False
        elif comment.startswith("X-Modules:"):
            modules = comment[10:].split()
            if not check_modules_installed(modules):
                return False

    return True


def combine_repos(build_path, version):
    global params
    repos_path = os.path.join(build_path, "custom/src/repos.yaml")

    cmd_system('printf "\\n\\n" >> "%s"' % repos_path)
    if params["enterprise-enabled"]:
        cmd_system(
            'cat "%s" >> "%s"'
            % (
                os.path.join(MIGRATION_PATH, "repos.enterprise.yaml"),
                repos_path,
            )
        )

    if not params["enterprise-enabled"] or version != params["start-version"]:
        if os.path.exists(build_path + "/custom/src/repos.custom.yml"):
            cmd_system('printf "\\n\\n" >> "%s"' % repos_path)
            cmd_system(
                'cat "%s" >> "%s"'
                % (
                    os.path.join(MIGRATION_PATH, "custom/src/repos.custom.yml"),
                    repos_path,
                )
            )


def copy_database(database, new_database, move_fs=False):
    logging.info('Backing up database & filestore to "%s"...' % new_database)
    try:
        cmd('dropdb "' + new_database + '"')
    except CommandFailedException:
        pass
    cmd('createdb "' + new_database + '" -T "' + database + '"')

    filestore_dir = os.path.join(os.environ["HOME"], ".local/share/Odoo/filestore/")
    filestore = os.path.join(filestore_dir, database)
    new_filestore = os.path.join(filestore_dir, new_database)
    if os.path.exists(filestore):
        if os.path.exists(new_filestore):
            cmd(["rm", "-r", new_filestore])
        if not move_fs:
            cmd(["cp", "-r", filestore, new_filestore])
        else:
            cmd(["mv", filestore, new_filestore])
    else:
        logging.warning("No filestore for %s to copy to %s." % (database, new_database))


def cmd(command, input=None, cwd=None):
    logging.debug(command)

    def enqueue_stream(stream, queue):
        for line in iter(stream.readline, ""):
            queue.put(line)
        stream.close()

    subprocess_args = {}
    if sys.version_info.minor >= 7:
        subprocess_args["capture_output"] = True
    if input:
        subprocess_args["input"] = input.encode("utf-8")

    proc = subprocess.Popen(
        command,
        bufsize=0,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=cwd or MIGRATION_PATH,
        universal_newlines=True,
        shell=isinstance(command, str),
    )

    # Write input
    if input:
        proc.stdin.write(input + "\n")
        proc.stdin.close()

    # Let another thread block on reading stderr
    q = Queue()
    t = Thread(target=enqueue_stream, args=(proc.stderr, q))
    t.daemon = True
    t.start()

    # Read stderr line by line
    stderrlines = ""
    while proc.poll() == None:
        try:
            line = q.get(timeout=1.0)
        except Empty:
            continue
        stderrlines += "[stderr]: " + line[:-1] + "\n"
        logging.debug("[stderr]: " + line[:-1])

    # Read stdout all in one go
    stdoutlines = ""
    for line in iter(proc.stdout.readline, ""):
        stdoutlines += "[stdout]: " + line[:-1] + "\n"
        logging.debug("[stdout]: " + line[:-1])

    if proc.returncode != 0:
        logging.error(stderrlines)
        logging.error(stdoutlines)
        raise CommandFailedException(command, proc.returncode)


def cmd_system(command):
    logging.debug(command)
    exit_code = os.system(command)
    if exit_code != 0:
        raise CommandFailedException(command, exit_code)


def defuse_database():
    queries = [
        ("UPDATE fetchmail_server SET active = FALSE, server = 'f'", False),
        ("UPDATE ir_cron SET active = FALSE", True),
        ("UPDATE ir_mail_server SET active = FALSE, smtp_host = 'f'", True),
    ]
    dbname = os.environ["PGDATABASE"]

    for query, required in queries:
        with psycopg.connect("dbname=" + dbname) as conn:
            with conn.cursor() as cur:
                try:
                    cur.execute(query)
                except Exception as e:
                    if required:
                        logging.error(
                            "Unable to defuse database, the following query failed:"
                        )
                        logging.error(query)
                        raise e


def find_db_version_from_progress():
    global params, progress
    highest_version = params["start-version"]
    for version, values in progress.items():
        if float(version) - float(highest_version) > 0.001:
            if (
                "upgrade" in values
                and values["upgrade"]
                or "enterprise" in values
                and values["enterprise"]
            ):
                highest_version = version
    return highest_version


def http_download(url):
    logging.debug("Downloading %s..." % url)
    with urlopen(url) as stream:
        response = stream.read()
        encoding = stream.headers.get_content_charset("utf-8")
        return response.decode(encoding)


def init_progress(version):
    global progress
    if not version in progress:
        progress[version] = {"hooks": {}}
    elif not "hooks" in progress[version]:
        progress[version]["hooks"] = {}


def load_defaults(params):
    enterprise_enabled = "MIGRATION_ENTERPRISE_ENABLED" in os.environ and os.environ[
        "MIGRATION_ENTERPRISE_ENABLED"
    ].lower() in ("1", "yes", "true")
    open_upgrade_disabled = (
        "MIGRATION_OPEN_UPGRADE_DISABLED" in os.environ
        and os.environ["MIGRATION_OPEN_UPGRADE_DISABLED"].lower()
        in ("1", "yes", "true")
    )
    start_version = (
        os.environ["MIGRATION_START_VERSION"]
        if "MIGRATION_START_VERSION" in os.environ
        else None
    )
    minimum_target = (
        os.environ["MIGRATION_ENTERPRISE_JUMP_TO"]
        if "MIGRATION_ENTERPRISE_JUMP_TO" in os.environ
        else ENTERPRISE_MINIMUM_TARGET
    )
    no_backups = (
        os.environ["MIGRATION_NO_BACKUPS"]
        if "MIGRATION_NO_BACKUPS" in os.environ
        else None
    )
    return {
        **{
            "enterprise-autotrust-ssh": False,
            "enterprise-dont-resume": False,
            "enterprise-enabled": enterprise_enabled,
            "enterprise-jump-to": minimum_target,
            "help": False,
            "no-backups": no_backups,
            "open-upgrade-disabled": open_upgrade_disabled,
            "production": False,
            "rebuild": False,
            "reset-progress": False,
            "restore": False,
            "start-version": start_version,
            "verbose": False,
        },
        **params,
    }


def load_enterprise_script():
    global params, enterprise_script_filepath

    def alter_code_block(prefix, postfix, replacement):
        i = code.find(prefix) + len(prefix)
        i = code.find("\n", i + 1) + 1
        j = code.find(postfix, i)
        j = code.find("\n", j + 1) + 1
        return code[:i] + replacement + "\n" + code[j:]

    code = http_download("https://upgrade.odoo.com/upgrade")

    # Replace the function body of get_upgraded_db_name
    start = "def get_upgraded_db_name(dbname, target, aim):"
    end = "\n    return"
    code = alter_code_block(
        start, end, "    return dbname + '-' + target + '-enterprise'"
    )

    # Replace the line that determines the logfile
    code = code.replace(
        "logging.basicConfig(",
        "logging.basicConfig(\n"
        '        filename="' + WAFT_DIR + '/logfile/%s-%s-enterprise.log"'
        " % (args.dbname, args.target),\n",
    )

    # Change SSH settings
    if params["enterprise-autotrust-ssh"]:
        code = code.replace(
            "-o IdentitiesOnly=yes",
            "-o IdentitiesOnly=yes "
            + "-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null",
        )
    else:
        known_hosts_filepath = os.path.join(MIGRATION_PATH, ".ssh-known-hosts")
        code = code.replace(
            "-o IdentitiesOnly=yes",
            "-o IdentitiesOnly=yes "
            + '-o \\"UserKnownHostsFile=%s\\"' % known_hosts_filepath,
        )

    # Write the file away and remember its path
    _, enterprise_script_filepath = mkstemp("-enterprise-upgrade.py")
    with open(enterprise_script_filepath, "w") as file:
        file.write(code)


def load_progress():
    global params

    HOOK_ORDER = [
        ("pre-migration", False, False),
        ("pre-upgrade", False, False),
        ("enterprise/pre-uprade", False, False),
        ("enterprise/post-upgrade", True, False),
        ("pre-openupgrade", True, False),
        ("post-upgrade", True, True),
        ("post-migration", True, True),
    ]

    progress_filepath = os.path.join(WAFT_DIR, "progress.json")
    if not os.path.exists(progress_filepath):
        return {}
    with open(progress_filepath, "r") as file:
        progress = json.load(file)

    # Remove the parts that are not necessary anymore
    if params["reset-progress"]:
        if len(params["reset-progress"]) > 1:
            version, hook = params["reset-progress"]
        else:
            version = params["reset-progress"][0]
            hook = "post-upgrade"
        i = [x[0] for x in HOOK_ORDER].index(hook)
        for j in range(i, len(HOOK_ORDER)):
            delete_hook, enterprise_done, upgrade_done = HOOK_ORDER[j]
            if (
                version in progress
                and "hooks" in progress[version]
                and delete_hook in progress[version]["hooks"]
            ):
                del progress[version]["hooks"][delete_hook]
                if not enterprise_done and "enterprise" in progress[version]:
                    del progress[version]["enterprise"]
                if not upgrade_done and "upgrade" in progress[version]:
                    del progress[version]["upgrade"]

        # Also, delete all higher versions from the progress dict
        version = params["reset-progress"][0]
        for v in [k for k in progress.keys()]:
            if float(v) > float(version):
                del progress[v]

    return progress


def mark_enterprise_done(version):
    if not version in progress:
        progress[version] = {"hooks": {}}
    progress[version]["enterprise"] = True
    save_progress()


def mark_upgrade_done(version):
    if not version in progress:
        progress[version] = {"hooks": {}}
    progress[version]["upgrade"] = True
    save_progress()


def mark_script_executed(version, hook_name, script_path):
    global progress
    if (
        version in progress
        and "hooks" in progress[version]
        and hook_name in progress[version]["hooks"]
    ):
        if script_path in progress[version]["hooks"][hook_name]:
            return False
    else:
        if version in progress and "hooks" in progress[version]:
            progress[version]["hooks"][hook_name] = []
        else:
            progress[version] = {"hooks": {hook_name: []}}
    progress[version]["hooks"][hook_name].append(script_path)
    save_progress()
    return True


def parse_arguments():
    arguments = {}

    try:
        optlist, args = getopt.getopt(
            sys.argv[1:],
            "d:ef:hoprsv",
            [
                "database=",
                "enterprise-enabled",
                "production",
                "start-version=",
                "help",
                "rebuild",
                "reset-progress=",
                "restore",
                "verbose",
                "enterprise-dont-resume",
                "enterprise-autotrust-ssh",
                "open-upgrade-disabled",
            ],
        )
    except getopt.GetoptError as err:
        print(err)
        return

    for opt in optlist:
        arg, value = opt

        if arg == "-d" or arg == "--database":
            arguments["database"] = value
        if arg == "-e" or arg == "--enterprise-enabled":
            arguments["enterprise-enabled"] = True
        if arg == "-f" or arg == "--start-version":
            arguments["start-version"] = value
        if arg == "-h" or arg == "--help":
            arguments["help"] = True
        if arg == "-o" or arg == "--open-upgrade-disabled":
            arguments["open-upgrade-disabled"] = True
        if arg == "-p" or arg == "--production":
            arguments["production"] = True
        if arg == "-r" or arg == "--rebuild":
            arguments["rebuild"] = True
        if arg == "--reset-progress":
            arguments["reset-progress"] = value.split(":")[:2]
        if arg == "-s" or arg == "--restore":
            arguments["restore"] = True
        if arg == "-v" or arg == "--verbose":
            arguments["verbose"] = True
        if arg == "--enterprise-dont-resume":
            arguments["enterprise-dont-resume"] = True
        if arg == "--enterprise-autotrust-ssh":
            arguments["enterprise-autotrust-ssh"] = True
        if arg == "--enterprise-jump-to":
            arguments["enterprise-jump-to"] = value
    return arguments


def pull_customer_database():
    global params
    customer_container = params["customer-container"]
    customer_database_name = params["customer-database-name"]

    _, tmp_file = mkstemp("-" + customer_database_name + ".sql")
    logging.info("Dumping customer database...")
    cmd(
        [
            "ssh",
            customer_container,
            "/usr/bin/pg_dump -O -x %s > /tmp/%s.sql"
            % (
                customer_database_name,
                customer_database_name,
            ),
        ]
    )
    logging.info("Downloading customer database...")
    cmd(
        [
            "scp",
            "%s:/tmp/%s.sql" % (customer_container, customer_database_name),
            tmp_file,
        ]
    )

    logging.info("Importing customer database...")
    try:
        cmd(["dropdb", os.environ["PGDATABASE"]])
    except CommandFailedException:
        pass
    cmd(["createdb", os.environ["PGDATABASE"]])
    cmd_system('psql -d "' + os.environ["PGDATABASE"] + '" < ' + tmp_file)
    logging.info("Customer database import succeeded.")


def parse_repos_config(filename):
    if not os.path.exists(filename):
        return []
    file = open(filename)
    config = yaml.load(file.read(), Loader=yaml.Loader)
    return config.keys()


def prepare():
    # Make sure the migration logfile already exists
    log_path = os.path.join(WAFT_DIR, "logfile")
    if not os.path.exists(log_path):
        os.mkdir(log_path)
    open(os.path.join(WAFT_DIR, "logfile/migration.log"), "a").close()

    # Make sure the migration dir exists
    if not os.path.exists(MIGRATION_PATH):
        os.mkdir(MIGRATION_PATH)


def run_python_script(build_dir, script_path):
    """Execute the given python script in the shell."""

    session_unopened = script_path.endswith("-unop.py")

    header = """
from __future__ import print_function
import os, sys, logging
from anybox.recipe.odoo.runtime.session import Session


MIGRATION_PATH = '%s'


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

logging.basicConfig(
    level=logging.DEBUG,
    stream=sys.stderr,
    format='%%(message)s'
)

__session = Session(os.path.join("%s", "auto/odoo.conf"), "%s")
""" % (
        MIGRATION_PATH,
        build_dir,
        build_dir,
    )

    if not session_unopened:
        header += """
__session.open()
env = __session.env
"""
    else:
        header += """
session = __session
"""

    header += """
with open("%s") as f:
    __script = f.read()
exec(__script)
""" % (
        script_path
    )

    if not session_unopened:
        header += """
__session.cr.commit()
__session.cr.close()
"""

    exec_path = os.path.join(build_dir, ".venv/bin/python")
    return cmd(exec_path, header)


def rebuild_sources():
    global params
    if not os.path.exists(MIGRATION_PATH):
        os.mkdir(MIGRATION_PATH)
        shutil.copytree(os.path.join(WAFT_DIR, "waftlib/migration"), MIGRATION_PATH)

    # Updates the .env-secret file of a build
    def write_env_secret(build_dir, version):
        overwrite_values = {
            "ODOO_VERSION": version,
            "PGDATABASE": os.environ["PGDATABASE"],
            "ODOO_DBFILTER": "^%s$" % os.environ["PGDATABASE"],
            "LOG_LEVEL": "DEBUG",
            # .env-secret files are generated with variables set to empty values causing issues.
            # This is a workaround for it.
            "PGPORT": "5432",
        }
        if "PGPASSWORD" in os.environ:
            overwrite_values["PGPASSWORD"] = os.environ["PGPASSWORD"]
        if params["enterprise-enabled"]:
            overwrite_values["DEFAULT_REPO_PATTERN_ODOO"] = (
                "https://github.com/odoo/odoo.git"
            )
        elif float(version) < 14.0 and version != params["start-version"]:
            overwrite_values["DEFAULT_REPO_PATTERN_ODOO"] = (
                "https://github.com/OCA/OpenUpgrade.git"
            )
        rewritten_lines = []

        lines = []
        env_secret_filename = os.path.join(build_dir, ".env-secret")
        if not os.path.exists(env_secret_filename):
            shutil.copyfile(
                os.path.join(WAFT_DIR, "waftlib/templates/.env-secret"),
                env_secret_filename,
            )
        with open(env_secret_filename, "rt") as file:
            # Go over all lines and see what needs to be rewritten
            for line in file:
                i = line.find("=")
                if i != -1:
                    key = line[:i].strip()

                    # Overwrite if necessary
                    if key in overwrite_values:
                        value = overwrite_values[key]
                        # No formatting/escaping of value is done, keep that in mind
                        lines.append('%s="%s"' % (key, value))
                        rewritten_lines.append(key)
                    else:
                        lines.append(line.strip())

        # Add lines for the missing values
        for key, value in overwrite_values.items():
            if not key in rewritten_lines:
                lines.append('%s="%s"' % (key, value))

        # Rewrite the file
        with open(os.path.join(build_dir, ".env-secret"), "wt") as file:
            for line in lines:
                file.write(line + "\n")

    def exclude_repos(config, whitelist):
        new_config = {}
        for repo_name in config:
            if repo_name in whitelist:
                new_config[repo_name] = config[repo_name]
        return new_config

    def prepare_odoo_entry(config, version):
        if not params["enterprise-enabled"]:
            odoo_repo_url = (
                "https://github.com/OCA/OpenUpgrade"
                if float(version) < 13.999
                else "https://github.com/OCA/OCB"
            )
            config["odoo"] = {
                "defaults": {"depth": "${WAFT_DEPTH_DEFAULT}"},
                "remotes": {"oca": odoo_repo_url},
                "merges": ["oca ${ODOO_VERSION}"],
            }
            if "ocb" in config:
                if odoo_repo_url in config["odoo"]["remotes"].values():
                    additional_remotes = {
                        k: v
                        for k, v in config["ocb"]["remotes"].items()
                        if not v.startswith(odoo_repo_url)
                    }
                    additional_merges = [
                        x
                        for x in config["ocb"]["merges"]
                        if x.split()[0] in additional_remotes
                    ]
                    config["odoo"]["remotes"].update(additional_remotes)
                    config["odoo"]["merges"] += additional_merges
                    # Delete the depth parameter when merges are available,
                    # because merges are not always maintained.
                    if len(config["odoo"]["merges"]) > 0:
                        del config["odoo"]["defaults"]["depth"]
                    if (
                        "defaults" in config["odoo"]
                        and "defaults" in config["ocb"]
                        and "depth" in config["ocb"]["defaults"]
                    ):
                        config["odoo"]["defaults"]["depth"] = config["ocb"]["defaults"][
                            "depth"
                        ]
                del config["ocb"]
            if float(version) > 13.999:
                config["openupgrade"] = {
                    "defaults": {"depth": "${WAFT_DEPTH_DEFAULT}"},
                    "remotes": {"oca": "https://github.com/OCA/OpenUpgrade"},
                    "merges": ["oca ${ODOO_VERSION}"],
                }
        else:
            config["odoo"] = {
                "defaults": {"depth": "${WAFT_DEPTH_DEFAULT}"},
                "remotes": {"odoo": "https://github.com/odoo/odoo"},
                "merges": ["odoo ${ODOO_VERSION}"],
            }

    repos_whitelist = [
        x
        for x in parse_repos_config(os.path.join(WAFT_DIR, "custom/src/old-repos.yaml"))
    ] + ["openupgrade"]
    default_repos_template_file = os.path.join(
        WAFT_DIR, "waftlib/migration/default-repos.yaml"
    )
    default_config = yaml.load(
        open(default_repos_template_file).read(), Loader=yaml.Loader
    )

    jump_to_version = (
        params["enterprise-jump-to"] if "enterprise-jump-to" in params else None
    )
    enterprise_enabled = (
        params["enterprise-enabled"] if "enterprise-enabled" in params else False
    )
    versions = (
        available_build_versions(params["start-version"])
        if not enterprise_enabled
        else available_enterprise_build_versions(
            params["start-version"], jump_to_version
        )
    )
    for version in versions:
        build_dir = os.path.join(MIGRATION_PATH, "build-" + version)
        if float(version) > 13.999 and version == os.environ["ODOO_VERSION"]:
            build_dir = WAFT_DIR
        elif params["open-upgrade-disabled"]:
            continue

        # Set up git in build dir
        if not os.path.exists(os.path.join(build_dir, "bootstrap")):
            cmd('mkdir -p "%s"' % build_dir)
            cmd("git init", cwd=build_dir)
            cmd(
                "git remote add sunflowerit https://github.com/sunflowerit/waft",
                cwd=build_dir,
            )
            if build_dir != WAFT_DIR:
                cmd("git pull sunflowerit master", cwd=build_dir)
                cmd("rm -rf .git", cwd=build_dir)

        logging.info("Rebuilding build-%s..." % version)

        repos_file = os.path.join(build_dir, "custom/src/repos.yaml")
        repos_file_existed = os.path.exists(repos_file)

        # Setup the build dir and bootstrap
        write_env_secret(build_dir, version)
        if build_dir != WAFT_DIR:
            cmd_system(os.path.join(build_dir, "bootstrap"))

        if not repos_file_existed:
            if version == params["start-version"]:
                if not os.path.exists(
                    os.path.join(WAFT_DIR, "custom/src/old-repos.yaml")
                ):
                    raise Exception(
                        "Put a copy of the original repos.yaml in custom/src/old-repos.yaml"
                    )
                shutil.copy(
                    os.path.join(WAFT_DIR, "custom/src/old-repos.yaml"), repos_file
                )
            else:
                # Construct a repos.yaml file from templates
                repos_template_file = (
                    WAFT_DIR + "/waftlib/migration/build-" + version + "/repos.yaml"
                )
                if os.path.exists(repos_template_file):
                    config = {
                        **default_config,
                        **yaml.load(
                            open(repos_template_file).read(), Loader=yaml.Loader
                        ),
                    }
                else:
                    config = copy.deepcopy(default_config)
                # The "ocb" entry is a special case that is merged into the "odoo" entry if needed
                prepare_odoo_entry(config, version)
                limited_config = exclude_repos(config, repos_whitelist)
                # Write down new repos.yaml
                file = open(repos_file, "w")
                raw_config = yaml.dump(limited_config, Dumper=yaml.Dumper)
                file.write(raw_config)
                file.close()

        # Build the build directory
        cmd_system(os.path.join(build_dir, "build"))
        cmd_system(
            os.path.join(build_dir, ".venv/bin/pip")
            + " install "
            + os.path.join(WAFT_DIR, "waftlib/migration/api")
        )
        cmd_system(
            os.path.join(build_dir, ".venv/bin/pip")
            + " install "
            + "git+https://github.com/anybox/anybox.recipe.odoo#egg=anybox.recipe.odoo"
        )
        cmd_system(
            os.path.join(build_dir, ".venv/bin/pip")
            + " install "
            + "git+https://github.com/sunflowerit/openupgradelib@fix-tax-tags-conversion"
        )

        # Change the config
        time.sleep(1)
        cmd_system("sed -i '/logfile =/d' \"" + build_dir + '/auto/odoo.conf"')
        logfile_path = (
            WAFT_DIR + "/logfile/" + os.environ["PGDATABASE"] + "-" + version + ".log"
        )
        cmd_system(
            'echo logfile = "'
            + logfile_path
            + '" >> "'
            + build_dir
            + '/auto/odoo.conf"'
        )
        if float(version) < 8.999:
            cmd_system("sed -i '/db_port =/d' \"" + build_dir + '/auto/odoo.conf"')
            cmd_system('echo "db_port = 5432"')
        if float(version) >= 13.999:
            try:
                cmd_system('rm -r "%s/custom/src/odoo/addons/*/migrations"' % build_dir)
            except:
                pass
            cmd_system("sed -i '/upgrade_path =/d' \"" + build_dir + '/auto/odoo.conf"')
            cmd_system(
                "sed -i '/server_wide_modules =/d' \"" + build_dir + '/auto/odoo.conf"'
            )
            cmd_system(
                'echo upgrade_path = "'
                + build_dir
                + '/custom/src/openupgrade/openupgrade_scripts/scripts" >> "'
                + build_dir
                + '/auto/odoo.conf"'
            )
            cmd_system(
                'echo server_wide_modules =  "openupgrade_framework" >> "'
                + build_dir
                + '/auto/odoo.conf"'
            )
        if float(version) <= 10.001:
            cmd_system('echo "running_env = dev" >> "' + build_dir + '/auto/odoo.conf"')


def rename_database(database, new_database):
    with psycopg.connect() as conn:
        with conn.cursor() as cur:
            cur.execute('ALTER DATABASE "%s" RENAME TO "%s"' % (database, new_database))


def run_enterprise_upgrade(version):
    global params, enterprise_script_filepath
    logging.info("Running enterprise upgrade to %s..." % version)

    def read_last_line(file):
        last_line = None
        for line in file:
            if line:
                last_line = line
            logging.info(line.decode("utf-8"))
        return last_line

    def check_process_status(proc):
        if proc.poll() == None:
            return False
        else:
            if proc.returncode != 0:
                if proc.returncode == 1:
                    last_line = read_last_line(proc.stderr).decode("utf-8")
                    if last_line.find("<urlopen error timed out>") != -1:
                        raise TimeoutError()
                    raise Exception(
                        "Enterprise upgrade failed with exit code "
                        + str(proc.returncode)
                    )
            # The logfile nor exit codes fully identify whether the upgrade has
            # finished. We check the presence of the restored database as a
            # means to identify that.
            try:
                # Fails if enterprise upgrade has not finished yet:
                psycopg.connect("dbname=" + enterprise_database)
                return True
            except psycopg.OperationalError:
                raise Exception("Enterprise upgrade failed")
        return False

    enterprise_database = os.environ["PGDATABASE"] + "-" + version + "-enterprise"
    enterprise_filestore = os.path.join(
        os.environ["HOME"], ".local/share/Odoo/filestore/", enterprise_database
    )
    try:
        cmd_system("dropdb " + enterprise_database + " 2>/dev/null")
    except CommandFailedException:
        pass
    cmd("rm -rf " + enterprise_filestore)

    log_filepath = os.path.join(
        WAFT_DIR,
        "logfile",
        os.environ["PGDATABASE"] + "-" + version + "-enterprise.log",
    )
    cmd_system('touch "' + log_filepath + '"')
    answer = (
        "n"
        if "enterprise-dont-resume" in params and params["enterprise-dont-resume"]
        else "Y"
    )
    done = False
    attempts = 0
    logfile = open(log_filepath, "r")
    logfile.seek(0, io.SEEK_END)
    # tty = open('/dev/tty', 'r')
    mode = "production" if params["production"] else "test"
    while not done:
        if attempts == 10:
            raise Exception("Enterprise upgrade failed, too many attempts.")
        attempts += 1

        try:
            proc = subprocess.Popen(
                [
                    "python3",
                    enterprise_script_filepath,
                    mode,
                    "-d",
                    os.environ["PGDATABASE"],
                    "-t",
                    version,
                ],
                stdin=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            # Keep reading the logfile until the process has exitted.
            while True:
                line = logfile.readline()
                if not line:
                    try:
                        if check_process_status(proc):
                            done = True
                            break
                        else:
                            time.sleep(1)
                            continue
                    except TimeoutError:
                        logging.warning("Timeout error, retrying...")
                        break

                if line.find("Error: Upgrade server communication error") != -1:
                    logging.warning("Timeout error, retrying...")
                    break
                elif (
                    line.find(
                        "This upgrade request seems to have been "
                        "interrupted. Do you want to resume it? "
                        "[Y/n]"
                    )
                    != -1
                ):
                    if answer == "Y":
                        logging.info("Resuming enterprise upgrade request...")
                    else:
                        logging.info("Restarting enterprise upgrade request...")
                    proc.stdin.write((answer + "\n").encode("utf-8"))
                    proc.stdin.flush()
                    answer = "Y"
        finally:
            proc.kill()

    mark_enterprise_done(version)
    try:
        if not params["no-backups"]:
            copy_database(enterprise_database, os.environ["PGDATABASE"], True)
        else:
            rename_database(enterprise_database, os.environ["PGDATABASE"])
    except CommandFailedException as e:
        logging.error(
            "Failed because we weren't able to get the enterprise database in "
            "place of the original one. No worries, the migrated database "
            "still exists, but someone needs to resolve the error, execute "
            "the following command, and restart the migration script:\n"
            f"createdb \"{os.environ['PGDATABASE']}\" -T "
            f'"{enterprise_database}"'
        )
        raise e


def run_migration(start_version, target_version):
    global params, db_version, progress

    start_version = db_version = params["start-version"]
    minimum_target = (
        params["enterprise-jump-to"]
        if "enterprise-jump-to" in params and params["enterprise-jump-to"]
        else ENTERPRISE_MINIMUM_TARGET
    )
    will_jump = params["enterprise-enabled"] and (float(start_version) + 1.0) < float(
        minimum_target
    )
    from_start = False

    if params["enterprise-enabled"]:
        load_enterprise_script()

    init_progress(start_version)
    progress_version = find_db_version_from_progress()
    from_start = abs(float(progress_version) - float(start_version)) < 0.001 and (
        not minimum_target in progress
        or (
            not "upgrade" in progress[minimum_target]
            or not progress[minimum_target]["upgrade"]
        )
        and (
            not "enterprise" in progress[minimum_target]
            or not progress[minimum_target]["enterprise"]
        )
    )

    logging.info("Defusing database...")
    defuse_database()

    #  Run the pre-migration scripts
    if from_start:
        if not db_version in progress or not (
            "upgrade" in progress[db_version] and progress[db_version]["upgrade"]
        ):
            run_scripts(db_version, "pre-migration")
        if params["enterprise-enabled"]:
            if not db_version in progress or not (
                "enterprise" in progress[db_version]
                and progress[db_version]["enterprise"]
            ):
                run_scripts(db_version, "enterprise/pre-migration")

    skip_initial_upgrade = (
        os.environ["SKIP_INITIAL_UPGRADE"] == "1"
        if "SKIP_INITIAL_UPGRADE" in os.environ
        else False
    )
    if from_start:
        if not skip_initial_upgrade and (
            not db_version in progress
            or not "upgrade" in progress[db_version]
            or not progress[db_version]["upgrade"]
        ):
            logging.info("Running initial upgrade...")
            run_upgrade(db_version)
    else:
        db_version = progress_version

    # Running an enterprise migration from the start, may require a 'jump'
    if params["enterprise-enabled"]:
        if from_start and (
            not start_version in progress
            or not (
                "enterprise" in progress[start_version]
                and progress[start_version]["enterprise"]
            )
        ):
            if will_jump:
                enterprise_done = (
                    minimum_target in progress
                    and "enterprise" in progress[minimum_target]
                    and progress[minimum_target]["enterprise"]
                )
                openupgrade_done = (
                    minimum_target in progress
                    and "upgrade" in progress[minimum_target]
                    and progress[minimum_target]["upgrade"]
                )
                if not enterprise_done:
                    run_scripts(minimum_target, "enterprise/pre-jump", start_version)
                    run_enterprise_upgrade(minimum_target)
                db_version = minimum_target
                if not openupgrade_done:
                    run_scripts(minimum_target, "enterprise/post-jump")
                    run_scripts(minimum_target, "enterprise/post-upgrade")
                    run_scripts(minimum_target, "post-upgrade")
        elif abs(float(progress_version) - float(minimum_target)) < 0.001:
            db_version = minimum_target
            if will_jump:
                run_scripts(minimum_target, "enterprise/post-jump")
            run_scripts(minimum_target, "enterprise/post-upgrade")
            run_scripts(minimum_target, "post-upgrade")

    # If not running from the start, we may need to call the
    # the post-upgrade scripts of the previous version.
    last_version = start_version
    for version in available_build_versions(start_version):
        if (
            version == start_version
            or float(db_version) - float(version) > 0.999
            or (
                params["enterprise-enabled"]
                and not version
                in available_enterprise_build_versions(start_version, minimum_target)
            )
        ):
            last_version = version
            continue
        enterprise_done, openupgrade_done = (False, False)
        if version in progress:
            if "enterprise" in progress[version]:
                enterprise_done = progress[version]["enterprise"]
            if "upgrade" in progress[version]:
                openupgrade_done = progress[version]["upgrade"]
        if enterprise_done or openupgrade_done:
            db_version = version

        init_progress(version)
        if not enterprise_done and not openupgrade_done:
            run_scripts(version, "pre-upgrade", last_version)
        if params["enterprise-enabled"]:
            if not enterprise_done and float(version) - float(minimum_target) > 0.001:
                run_scripts(version, "enterprise/pre-upgrade", last_version)
                run_enterprise_upgrade(version)
                db_version = version
            if not openupgrade_done:
                run_scripts(version, "enterprise/post-upgrade")
        if not params["open-upgrade-disabled"] and not openupgrade_done:
            run_scripts(version, "pre-openupgrade")
            logging.info("Running OpenUpgrade to %s..." % version)
            run_upgrade(version)
        db_version = version
        run_scripts(version, "post-upgrade")
        last_version = version

    if params["enterprise-enabled"]:
        run_scripts(db_version, "enterprise/post-migration")
    run_scripts(db_version, "post-migration")


def run_script(script_path, run_at_version=None):
    global config, db_version
    final_version = os.environ["ODOO_VERSION"]
    if not run_at_version:
        run_at_version = db_version
    logging.info("Running script %s..." % script_path)

    build_dir = (
        WAFT_DIR
        if run_at_version == final_version and float(run_at_version) > 13.999
        else MIGRATION_PATH + "/build-" + run_at_version
    )
    if script_path.endswith(".py"):
        run_python_script(build_dir, script_path)
    elif script_path.endswith(".sh"):
        cmd(["bash", script_path], None, cwd=build_dir)
    elif script_path.endswith(".sql"):
        script_content = "\\set ON_ERROR_STOP true\n" + open(script_path, "r").read()
        cmd("psql -d " + os.environ["PGDATABASE"], script_content)
    elif script_path.endswith(".link"):
        actual_subpath = open(script_path).readline().strip()
        actual_script_path = MIGRATION_PATH + "/hook/common/" + actual_subpath
        if os.path.exists(actual_script_path):
            return run_script(actual_script_path, run_at_version)
        actual_script_path = (
            WAFT_DIR + "/waftlib/migration/hook/common/" + actual_subpath
        )
        if os.path.exists(actual_script_path):
            return run_script(actual_script_path, run_at_version)
        raise Exception('Script "%s" not found' % actual_subpath)
    else:
        return False
    return True


def run_scripts(version, hook_name, run_at_version=None):
    global config, progress

    logging.info("Loading %s %s scripts..." % (version, hook_name))
    if not run_at_version:
        run_at_version = version

    def listdir_full_paths(path):
        if not os.path.exists(path):
            return []
        return [
            (filename, os.path.join(path, filename)) for filename in os.listdir(path)
        ]

    scripts_path1 = os.path.join(WAFT_DIR, "waftlib/migration/hook", hook_name)
    scripts_path2 = os.path.join(MIGRATION_PATH, "hook", hook_name)
    scripts_path3 = os.path.join(
        WAFT_DIR, "waftlib/migration/build-" + version, "hook", hook_name
    )
    scripts_path4 = os.path.join(MIGRATION_PATH, "build-" + version, "hook", hook_name)
    scripts = (
        listdir_full_paths(scripts_path1)
        + listdir_full_paths(scripts_path2)
        + listdir_full_paths(scripts_path3)
        + listdir_full_paths(scripts_path4)
    )

    for script_filename, script_path in sorted(scripts, key=lambda x: x[0]):
        if (
            version in progress
            and "hooks" in progress[version]
            and hook_name in progress[version]["hooks"]
            and script_path in progress[version]["hooks"][hook_name]
        ):
            continue
        if not check_script_support(script_path, run_at_version):
            continue

        if not run_script(script_path, run_at_version):
            logging.error(
                "Unknown file extension for script " + script_filename + ", skipping..."
            )
            continue

        mark_script_executed(version, hook_name, script_path)


def run_upgrade(version):
    global params

    instance = os.environ["PGDATABASE"] + "-" + version
    final_version = os.environ["ODOO_VERSION"]
    build_dir = (
        WAFT_DIR
        if version == final_version and float(version) >= 14.0
        else MIGRATION_PATH + "/build-" + version
    )

    logfile = os.path.join(WAFT_DIR, "logfile", instance + ".log")
    args = (
        '-u base --stop-after-init --load=openupgrade_framework --logfile "%s"'
        % logfile
    )
    cmd(build_dir + "/run " + args)
    mark_upgrade_done(version)

    logging.info("Defusing database...")
    defuse_database()

    # Backup the database
    if not params["no-backups"]:
        copy_database(
            os.environ["PGDATABASE"], os.environ["PGDATABASE"] + "-" + version
        )


def save_progress():
    global progress
    progress_filepath = os.path.join(WAFT_DIR, "progress.json")
    with open(progress_filepath, "w") as file:
        json.dump(progress, file, indent=2)


def setup_logging():
    log_filepath = os.path.join(WAFT_DIR, "logfile/migration.log")
    log_level = os.environ["WAFT_LOG_LEVEL"]
    log_file_handler = logging.FileHandler(log_filepath)
    log_file_handler.setLevel(logging.DEBUG)
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(log_level)
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[log_file_handler, stream_handler],
    )


def verify_arguments(args: dict):
    return True


def verify_params():
    global params
    if not "PGDATABASE" in os.environ or not os.environ["PGDATABASE"]:
        logging.error("No database specified in the environment as PGDATABASE.")
        return False
    if not "start-version" in params or not params["start-version"]:
        logging.error(
            "No start version specified. Use either --start-version on the command line, or MIGRATION_START_VERSION in the environment."
        )
        return False
    return True


def main():
    global params, progress

    os.environ["MIGRATION_PATH"] = MIGRATION_PATH

    try:
        args = parse_arguments()
        if args == None or not verify_arguments(args):
            return 1

        if "help" in args:
            print(HELP_TEXT)
            return 0

        prepare()
        params = load_defaults(args)
        if not verify_params():
            return 1
        setup_logging()

        if params["rebuild"]:
            logging.info("Rebuilding sources...")
            rebuild_sources()
            return 0

        progress = load_progress()
        logging.debug("Loaded progress: " + str(progress))

        if params["restore"]:
            if progress:
                logging.error(
                    "You have chosen to restore from the customer database, but there is still progress saved."
                )
                logging.error(
                    "To restore the customer database, remove the progress.json file."
                )
                return
            else:
                pull_customer_database()

        start_version = (
            params["reset-progress"][0]
            if params["reset-progress"]
            else params["start-version"]
        )
        target_version = os.environ["ODOO_VERSION"]
        logging.info(
            "Starting migration from %s to %s...", start_version, target_version
        )
        run_migration(start_version, target_version)
        logging.info("Migration completed.")
    except Exception as e:
        type, name, tb = sys.exc_info()
        stacktrace = traceback.format_tb(tb)
        logging.error(
            "%s was raised: %s\nStacktrace:\n%s"
            % (type.__name__, e, "".join(stacktrace))
        )
        exit(1)


main()
