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
import shutil
import subprocess
import sys
from tempfile import mkstemp
import time
from threading import Thread
import traceback
from urllib.request import urlopen
from queue import Queue, Empty
import yaml


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
    def __init__(self, command: str | list[str], exit_code: int):
        """
        A failed command execution.

        :param command: The command which failed execution.
        :param exit_code: The exit code of the command execution.
        """
        self.command = command
        self.exit_code = exit_code

    def __str__(self):
        return "The following command failed with exit code %s: %s" % (
            str(self.exit_code),
            self.command,
        )


def available_enterprise_build_versions(start_version, minimum_target):
    """
    Get a list of all Odoo versions which need a build folder for the migration.

    Does not include the versions which are skipped by Odoo's own official migration
    script.
    """
    return [
        version
        for version in available_build_versions(start_version)
        if version == start_version or float(version) - float(minimum_target) >= -0.01
    ]


def available_build_versions(start_version):
    """Get a list of all Odoo versions which need a build folder for the migration."""
    end_version = floor(float(os.environ["ODOO_VERSION"]))
    return [str(x) + ".0" for x in range(floor(float(start_version)), end_version + 1)]


def backup_mail_server_info():
    """Back up the mail server tables in the database."""
    queries = [
        (
            """
            CREATE TABLE IF NOT EXISTS fetchmail_server_backup AS
            SELECT * FROM fetchmail_server
        """,
            False,
        ),
        (
            """
            CREATE TABLE IF NOT EXISTS ir_mail_server_backup AS
            SELECT * FROM ir_mail_server
        """,
            True,
        ),
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


def check_modules_installed(modules: str):
    """
    Check whether or not the given `modules` are installed in the current database.
    """
    with psycopg.connect("dbname=" + os.environ["PGDATABASE"]) as conn:
        with conn.cursor() as cur:
            for module in modules:
                cur.execute(
                    """
                    SELECT * FROM ir_module_module WHERE
                    state NOT IN ('uninstalled', 'uninstallable')
                    AND name = %s
                    """,
                    [module],
                )
                if not cur.rowcount:
                    return False
    return True


def check_script_support(filename, version):
    """
    Check wether the specified script is supported.

    The given version and the currently installed modules are considered.
    """
    comment_prefix = "--" if filename.endswith(".sql") else "#"

    with open(filename, "r") as file:
        for line in file:
            stripped_line = line.strip()
            # Only parse comments in the top of the file
            if not stripped_line.startswith(comment_prefix):
                break

            comment = stripped_line[len(comment_prefix):].strip()
            if comment.startswith("X-Supports:"):
                versions = [x.strip() for x in comment[11:].split()]
                if version not in versions:
                    return False
            elif comment.startswith("X-Modules:"):
                modules = comment[10:].split()
                if not check_modules_installed(modules):
                    return False

    return True


def combine_repos(build_path, version):
    """
    Combine the repositories into a single repos.yaml file.

    Creates a repos.yaml file from the repos.custom.yaml & repos.enterprise.yaml files.
    """
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


def copy_database(database: str, new_database: str, move_fs: bool = False):
    """
    Copy the database (and filestore) to a new database.

    :param database: The database to copy.
    :param new_database: The name of the new database to create.
    :param move_fs: Whether to move the filestore rather than copy it.
    """
    logging.info('Backing up database & filestore to "%s"...' % new_database)
    try:
        cmd(["dropdb", new_database], suppress_stderr=True, suppress_stdout=True)
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
            cmd(["cp", "-rl", filestore, new_filestore])
        else:
            cmd(["mv", filestore, new_filestore])
    else:
        logging.warning("No filestore for %s to copy to %s." % (database, new_database))


def cmd(
    command: list[str], input_: str | None = None, cwd: str | None = None,
    suppress_stderr: bool = False, suppress_stdout: bool = False
):
    """
    Run a command.

    :param command: The command to run, formatted as a list of strings.
    :param input: Some text to immediately send to the input of the command, as UTF-8.
    :param cwd: The working directory in which the command will be executed. When not
        set, will default to migration directory of the main build folder.
    :param suppress_stderr: Whether to suppress the standard error output.
    :param suppress_stdout: Whether to suppress the standard output.
    """
    logging.debug(command)

    def enqueue_stream(stream, queue):
        for line in iter(stream.readline, ""):
            queue.put(line)
        stream.close()

    subprocess_args = {}
    if sys.version_info.minor >= 7:
        subprocess_args["capture_output"] = True
    if input_:
        subprocess_args["input"] = input_.encode("utf-8")

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
    if input_:
        proc.stdin.write(input_ + "\n")
        proc.stdin.close()

    # Let another thread block on reading stderr
    q = Queue()
    t = Thread(target=enqueue_stream, args=(proc.stderr, q))
    t.daemon = True
    t.start()

    # Read stderr line by line
    stderrlines = ""
    while proc.poll() is None:
        try:
            line = q.get(timeout=1.0)
        except Empty:
            continue
        if not suppress_stderr:
            stderrlines += "[stderr]: " + line[:-1] + "\n"
            logging.debug("[stderr]: " + line[:-1])

    # Read stdout all in one go
    stdoutlines = ""
    for line in iter(proc.stdout.readline, ""):
        if not suppress_stderr:
            stdoutlines += "[stdout]: " + line[:-1] + "\n"
            logging.debug("[stdout]: " + line[:-1])

    if proc.returncode != 0:
        if not suppress_stderr and stderrlines:
            logging.error(stderrlines)
        if not suppress_stdout and stdoutlines:
            logging.error(stdoutlines)
        raise CommandFailedException(command, proc.returncode)


def cmd_system(command: str):
    """
    Run the givin system command.

    The standard output and error output should generally show up in the terminal.
    """
    logging.debug(command)
    exit_code = os.system(command)
    if exit_code != 0:
        raise CommandFailedException(command, exit_code)


def defuse_database():
    """
    Disable some stuff in the database.

    This is to prevent the things from running that we don't
    want to have running.
    """
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
    """Extract the current Odoo version of the database from the current progress."""
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


def http_download(url: str):
    """Download the HTTP body from the specified URL."""
    logging.debug("Downloading %s..." % url)
    with urlopen(url) as stream:
        response = stream.read()
        encoding = stream.headers.get_content_charset("utf-8")
        return response.decode(encoding)


def init_progress(version):
    """Initialize the global progress variable."""
    if version not in progress:
        progress[version] = {"hooks": {}}
    elif "hooks" not in progress[version]:
        progress[version]["hooks"] = {}


def load_defaults(parameters):
    """
    Load the parameters from any present environment variables.

    Applies defaults wherever they are not yet set.
    """
    def is_environ_bool_true(name):
        return name in os.environ and os.environ[name].lower() in ("1", "yes", "true")

    enterprise_enabled = is_environ_bool_true("MIGRATION_ENTERPRISE_ENABLED")
    open_upgrade_disabled = is_environ_bool_true("MIGRATION_OPEN_UPGRADE_DISABLED")
    skip_initial_upgrade = is_environ_bool_true("SKIP_INITIAL_UPGRADE")
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
    no_backups = is_environ_bool_true("MIGRATION_NO_BACKUPS")
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
            "skip-initial-upgrade": skip_initial_upgrade,
            "start-version": start_version,
            "verbose": False,
        },
        **parameters,
    }


def load_enterprise_script():
    """
    Download and save the migration script in a temporary location.

    The file path is stored in the global variable `enterprise_script_filepath`.
    """
    global enterprise_script_filepath

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
    """
    Load the progress.json file from the waft build directory.

    It will be put into the global progress variable.
    """
    global progress
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
        for v in list(progress.keys()):
            if float(v) > float(version):
                del progress[v]

    return progress


def mark_enterprise_done(version):
    """
    Remember that we have completed the 'enterprise upgrade' targetting a version.

    This means that the core - and enterprise modules have been upgraded to this
    version, but none of the other modules.
    """
    if version not in progress:
        progress[version] = {"hooks": {}}
    progress[version]["enterprise"] = True
    save_progress()


def mark_upgrade_done(version):
    """
    Remember that we completed the 'OpenUpgrade upgrade' towards the given version.

    This means that all modules of this version should have been upgraded.
    """
    if version not in progress:
        progress[version] = {"hooks": {}}
    progress[version]["upgrade"] = True
    save_progress()


def mark_script_executed(version, hook_name, script_path):
    """
    Remember that we have succesfully executed a certain script during the migration.
    """
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
    """Parse the command line arguments."""
    arguments = {}

    try:
        optlist, _args = getopt.getopt(
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

        if arg in ("-d" or "--database"):
            arguments["database"] = value
        if arg in ("-e" or "--enterprise-enabled"):
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


def parse_repos_config(filename):
    """Load and parse a repos.yaml file."""
    if not os.path.exists(filename):
        return []
    with open(filename) as file:
        config = yaml.load(file.read(), Loader=yaml.Loader)
    return config.keys()


def prepare():
    """Do some stuff in preparation of running the migration."""
    # Make sure the migration logfile already exists
    log_path = os.path.join(WAFT_DIR, "logfile")
    if not os.path.exists(log_path):
        os.mkdir(log_path)
    open(os.path.join(WAFT_DIR, "logfile/migration.log"), "a").close()

    # Make sure the migration dir exists
    if not os.path.exists(MIGRATION_PATH):
        os.mkdir(MIGRATION_PATH)


def run_python_script(build_dir, script_path):
    """Execute the given python script in an Odoo env using click-odoo."""
    # This path is equivalent to what was used by Session before
    odoo_conf = os.path.join(build_dir, "auto", "odoo.conf")

    header = """
from __future__ import print_function
import os
import sys
import logging

import odoo
from odoo.tools import config as odoo_config
from click_odoo import OdooEnvironment

MIGRATION_PATH = %r
ODOO_CONF = %r

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

logging.basicConfig(
    level=logging.DEBUG,
    stream=sys.stderr,
    format='%%(message)s'
)

# Initialize Odoo configuration from the odoo.conf file
# This is equivalent to: odoo-bin -c ODOO_CONF
odoo_config.parse_config(["-c", ODOO_CONF])

db_name = odoo_config.get("db_name")
if not db_name:
    eprint("No 'db_name' found in Odoo configuration %%r" %% ODOO_CONF)
    sys.exit(1)

# Create an Environment using click-odoo's OdooEnvironment context manager
with OdooEnvironment(database=db_name) as env:
    # Make env visible to the migration script
    globals()["env"] = env

    # Execute the migration script
    with open(%r) as f:
        __script = f.read()
    exec(__script, globals())
""" % (
        MIGRATION_PATH,
        odoo_conf,
        script_path,
    )

    exec_path = os.path.join(build_dir, ".venv/bin/python")
    return cmd(exec_path, header)


def rebuild_sources():
    """
    (Re)build all Waft build folders that are part of this migration build.

    This includes all the build folders in the ./migration folder, and it also includes
    the main Waft build.
    """
    if not os.path.exists(MIGRATION_PATH):
        os.mkdir(MIGRATION_PATH)
        shutil.copytree(os.path.join(WAFT_DIR, "waftlib/migration"), MIGRATION_PATH)

    # Updates the .env-secret file of a build
    def write_env_secret(build_dir, version):
        """Generate a .env-secret file for a particular build folder."""
        overwrite_values = {
            "ODOO_VERSION": version,
            "PGDATABASE": os.environ["PGDATABASE"],
            "ODOO_DBFILTER": "^%s$" % os.environ["PGDATABASE"],
            "LOG_LEVEL": "DEBUG",
            # .env-secret files are by default generated with variables set to empty
            # values, which causes issues with PGPORT, because the empty value will
            # actually be tried as a port.
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
            if key not in rewritten_lines:
                lines.append('%s="%s"' % (key, value))

        # Rewrite the file
        with open(os.path.join(build_dir, ".env-secret"), "wt") as file:
            for line in lines:
                file.write(line + "\n")

    def exclude_repos(config: dict, whitelist: list[str]):
        """
        Get a filtered copy of the given config dictinary.

        Only the top-level entries with a name found in the whitelist will be taken.
        """
        new_config = {}
        for repo_name in config:
            if repo_name in whitelist:
                new_config[repo_name] = config[repo_name]
        return new_config

    def prepare_odoo_entry(config, version):
        """Construct a repos.yaml repository entry."""
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

    repos_whitelist = parse_repos_config(
        os.path.join(WAFT_DIR, "custom/src/old-repos.yaml")
    )
    repos_whitelist = list(repos_whitelist) + ["openupgrade"]
    default_repos_template_file = os.path.join(
        WAFT_DIR, "waftlib/migration/default-repos.yaml"
    )
    with open(default_repos_template_file, 'r') as file:
        default_config = yaml.load(
            file.read(), Loader=yaml.Loader
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
                        "Put a copy of the original repos.yaml in "
                        "custom/src/old-repos.yaml"
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
                    with open(repos_template_file) as file:
                        config = {
                            **default_config,
                            **yaml.load(
                                file.read(), Loader=yaml.Loader
                            ),
                        }
                else:
                    config = copy.deepcopy(default_config)
                # The "ocb" entry is a special case that is merged into the "odoo" entry
                # if needed
                prepare_odoo_entry(config, version)
                limited_config = exclude_repos(config, repos_whitelist)
                # Write down new repos.yaml
                with open(repos_file, "w") as file:
                    raw_config = yaml.dump(limited_config, Dumper=yaml.Dumper)
                    file.write(raw_config)

        # Build the build directory
        cmd_system(os.path.join(build_dir, "build"))
        cmd_system(
            os.path.join(build_dir, ".venv/bin/pip")
            + " install "
            + os.path.join(WAFT_DIR, "waftlib/migration/api")
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
            cmd_system("sed -i '/upgrade_path =/d' \"" + build_dir + '/auto/odoo.conf"')
            cmd_system(
                "sed -i '/server_wide_modules =/d' \"" + build_dir + '/auto/odoo.conf"'
            )
            start_version = (
                os.environ["MIGRATION_START_VERSION"]
                if "MIGRATION_START_VERSION" in os.environ
                else None
            )
            if version != start_version:
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
    """Rename the database."""
    try:
        cmd(["dropdb", new_database], suppress_stderr=True, suppress_stdout=True)
    except CommandFailedException:
        pass
    with psycopg.connect("dbname=postgres") as conn:
        with conn.cursor() as cur:
            cur.execute('ALTER DATABASE "%s" RENAME TO "%s"' % (database, new_database))


def run_enterprise_upgrade(version: str):
    """
    Run Odoo's official enterprise migration script.

    :param version: The target odoo version to run the script for. The version that the
        database gets upgraded to.
    """
    logging.info("Running enterprise upgrade to %s..." % version)

    def read_last_line(file):
        last_line = None
        for line in file:
            if line:
                last_line = line
            logging.info(line.decode("utf-8"))
        return last_line

    def check_process_status(proc):
        if proc.poll() is None:
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
        cmd(
            'dropdb "' + enterprise_database + '"',
            suppress_stderr=True,
            suppress_stdout=True,
        )
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
                    "--debug",
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
    """Run the migration process, from start to finish."""
    global params, db_version

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
        minimum_target not in progress
        or (
            "upgrade" not in progress[minimum_target]
            or not progress[minimum_target]["upgrade"]
        )
        and (
            "enterprise" not in progress[minimum_target]
            or not progress[minimum_target]["enterprise"]
        )
    )

    logging.info("Backing up mail server and defusing database...")
    backup_mail_server_info()
    defuse_database()

    #  Run the pre-migration scripts
    if from_start:
        if db_version not in progress or not (
            "upgrade" in progress[db_version] and progress[db_version]["upgrade"]
        ):
            run_scripts(db_version, "pre-migration")
        if params["enterprise-enabled"]:
            if db_version not in progress or not (
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
            db_version not in progress
            or "upgrade" not in progress[db_version]
            or not progress[db_version]["upgrade"]
        ):
            logging.info("Running initial upgrade...")
            run_upgrade(db_version)
    else:
        db_version = progress_version

    # Running an enterprise migration from the start, may require a 'jump'
    if params["enterprise-enabled"]:
        if from_start and (
            start_version not in progress
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
                and version not in
                available_enterprise_build_versions(start_version, minimum_target)
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
        going_to_upgrade = (
            not params["open-upgrade-disabled"] and not openupgrade_done
        ) or not enterprise_done
        if going_to_upgrade:
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


def run_script(script_path: str, run_at_version: str | None = None):
    """
    Run the script at the given filepath.

    This can be a Python (.py) script (that will run in a Odoo shell.
    This can be a .sql file with PostgresQL queries.
    Or this can be a shell (.sh) script, that has some environment variables available.

    :param script_path: The filepath of the script.
    :param run_at_version: The Odoo version of the build that will be used to run the
        Odoo shell.
    """
    final_version = os.environ["ODOO_VERSION"]
    if not run_at_version:
        run_at_version = db_version
    logging.info("Running script %s...", script_path)

    build_dir = (
        WAFT_DIR
        if run_at_version == final_version and float(run_at_version) > 13.999
        else MIGRATION_PATH + "/build-" + run_at_version
    )
    if script_path.endswith(".py"):
        run_python_script(build_dir, script_path)
    elif script_path.endswith(".sh"):
        cmd(["bash", script_path], cwd=build_dir)
    elif script_path.endswith(".sql"):
        with open(script_path, "r") as file:
            script_content = "\\set ON_ERROR_STOP true\n" + file.read()
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


def run_scripts(version: str, hook_name: str, run_at_version: str | None = None):
    """
    Run all the available scripts for a particular Odoo version and a specific hook.
    """

    logging.info("Loading %s %s scripts...", version, hook_name)
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
    """Run a full upgrade to the given Odoo version."""
    instance = os.environ["PGDATABASE"] + "-" + version
    final_version = os.environ["ODOO_VERSION"]
    build_dir = (
        WAFT_DIR
        if version == final_version and float(version) >= 14.0
        else MIGRATION_PATH + "/build-" + version
    )
    logfile = os.path.join(WAFT_DIR, "logfile", instance + ".log")
    start_version = (
        os.environ["MIGRATION_START_VERSION"]
        if "MIGRATION_START_VERSION" in os.environ
        else None
    )
    if version == start_version:
        if params["verbose"]:
            args = (
                f'-u base --log-level=debug_sql --log-handler=odoo.modules.loading:DEBUG --logfile "{logfile}" --stop-after-init'
            )
        else:
            args = (
                f'-u base --logfile "{logfile}" --stop-after-init'
            )
    else:
        if params["verbose"]:
            args = (
                f'-u base --load=openupgrade_framework --log-level=debug_sql --log-handler=odoo.modules.loading:DEBUG --log-handler=odoo.modules.migration:DEBUG --logfile "{logfile}" --stop-after-init'
            )
        else:
            args = (
                f'-u base --load=openupgrade_framework --logfile "{logfile}" --stop-after-init'
            )
    cmd(build_dir + "/run " + args)

    logging.info("Defusing database...")
    defuse_database()

    # Backup the database
    if not params["no-backups"]:
        database = os.environ["PGDATABASE"]
        backup_database = database + "-" + version
        try:
            copy_database(database, backup_database)
        except CommandFailedException as e:
            logging.error(
                "Failed to back up the database. No worries, the migrated "
                "database still exists, but someone needs to resolve the "
                "error, execute the following command, and restart the "
                "migration script:\n"
                'createdb "%s" -T "%s"',
                backup_database,
                database,
            )
            raise e
    mark_upgrade_done(version)


def save_progress():
    """
    Write all the progress information from the global variable into a file.

    It is the progress.json file in the main Waft build directory.
    """
    progress_filepath = os.path.join(WAFT_DIR, "progress.json")
    with open(progress_filepath, "w") as file:
        json.dump(progress, file, indent=2)


def setup_logging():
    """Initialize the logger."""
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


def verify_params():
    """Verify all parameters."""
    if not params["rebuild"] and (
        "PGDATABASE" not in os.environ or not os.environ["PGDATABASE"]
    ):
        logging.error("No database specified in the environment as PGDATABASE.")
        return False
    if "start-version" not in params or not params["start-version"]:
        logging.error(
            "No start version specified. Use either --start-version on the command "
            "line, or MIGRATION_START_VERSION in the environment."
        )
        return False
    return True


def main():
    """Run the migration script."""
    global params, progress

    os.environ["MIGRATION_PATH"] = MIGRATION_PATH

    try:
        args = parse_arguments()
        if args is None:
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
        logging.debug("Loaded progress: %s", progress)

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
        _type, _name, tb = sys.exc_info()
        stacktrace = traceback.format_tb(tb)
        logging.error(
            "%s was raised: %s\nStacktrace:\n%s"
            % (type.__name__, e, "".join(stacktrace))
        )
        return 1
    return 0


exit_code = main()
sys.exit(exit_code)
