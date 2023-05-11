#!/usr/bin/env python3
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
from threading  import Thread
import traceback
from urllib.request import urlopen
from queue import Queue, Empty


# Adjust this to the minimum supported target version by the enterprise script
# whenever Odoo decides to change it.
ENTERPRISE_MINIMUM_TARGET = "13.0"
HELP_TEXT = """
Parameters
===================

--database NAME
-d NAME     Specify a databasename that overrides the name from the
            configuration file.
--enterprise-enabled
-e          Enable the enterprise migration scripts as well.
--first-version VERSION
-f VERSION  Start migration from a database of this Odoo version. This could
            prevent pre-migration scripts from running.
--help
-h          Show this help message.
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
MIGRATION_PATH = WAFT_DIR + '/migration'

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
            self.command
        )


def available_enterprise_build_versions(start_version):
    return [
        version for version in available_build_versions(start_version)
        if version == start_version or float(version) - float(ENTERPRISE_MINIMUM_TARGET) >= -0.01
    ]


def available_build_versions(start_version):
    global params
    end_version = floor(float(os.environ['ODOO_VERSION']))
    return [str(x) + '.0' for x in range(floor(float(start_version)), end_version+1)]

def check_modules_installed(modules):
    """Returns whether or not the given `modules` are installed in the
       current database.
    """
    with psycopg.connect("dbname=" + os.environ['PGDATABASE']) as conn:
        with conn.cursor() as cur:
            for module in modules:
                cur.execute("SELECT * FROM ir_module_module WHERE "
                            "state <> 'uninstalled' AND name = %s",
                            [module])
                if not cur.rowcount:
                    return False
    return True


def check_script_support(filename, version, from_version):
    comment_prefix = '--' if filename.endswith('.sql') else '#'
    file = open(filename, 'r')

    for line in file:
        stripped_line = line.strip()
        # Only parse comments in the top of the file
        if not stripped_line.startswith(comment_prefix):
            break
        
        comment = stripped_line[len(comment_prefix):].strip()
        if comment.startswith('X-Supports:'):
            versions = [x.strip() for x in comment[11:].split()]
            if not version in versions:
                return False
        elif from_version and comment.startswith('X-Supports-From:'):
            versions = [x.strip() for x in comment[11:].split()]
            if not from_version in versions:
                return False
        elif comment.startswith('X-Modules:'):
            modules = comment[10:].split()
            if not check_modules_installed(modules):
                return False

    return True


def combine_repos(build_path, version):
    global params
    repos_path = os.path.join(build_path, 'custom/src/repos.yaml')

    cmd_system('printf "\\n\\n" >> \"%s\"' % repos_path)
    if params['enterprise-enabled']:
        cmd_system('cat "%s" >> "%s"' % (
            os.path.join(MIGRATION_PATH, 'repos.enterprise.yaml'),
            repos_path,
        ))

    if not params['enterprise-enabled'] or version != params['start-version']:
        if os.path.exists(build_path + '/custom/src/repos.custom.yml'):
            cmd_system('printf "\\n\\n" >> \"%s\"' % repos_path)
            cmd_system('cat "%s" >> "%s"' % (
                os.path.join(MIGRATION_PATH, 'custom/src/repos.custom.yml'),
                repos_path,
            ))


def copy_database(database, new_database):
    try:
        cmd('dropdb \"' + new_database + '\"')
    except CommandFailedException:
        pass
    cmd('createdb \"' + new_database + '\" -T \"' + database + '\"')

    filestore_dir = os.path.join(
        os.environ['HOME'],
        '.local/share/Odoo/filestore/'
    )
    filestore = os.path.join(filestore_dir, database)
    new_filestore = os.path.join(filestore_dir, new_database)
    if os.path.exists(filestore):
        if os.path.exists(new_filestore):
            cmd(['rm', '-r', new_filestore])
        cmd(['cp', '-r', filestore, new_filestore])
    else:
        logging.warn("No filestore for %s to copy to %s." % (database, new_database))


def cmd(command, input=None, cwd=None):
    logging.debug(command)

    def enqueue_stream(stream, queue):
        for line in iter(stream.readline, ''):
            queue.put(line)
        stream.close()

    subprocess_args = {}
    if sys.version_info.minor >= 7:
        subprocess_args['capture_output'] = True
    if input:
        subprocess_args['input'] = input.encode('utf-8')

    proc = subprocess.Popen(command,
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
        proc.stdin.write(input + '\n')
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
    for line in iter(proc.stdout.readline, ''):
        stdoutlines += "[stdout]: " + line[:-1] + "\n"
        logging.debug('[stdout]: ' + line[:-1])

    if proc.returncode != 0:
        logging.error(stderrlines)
        logging.error(stdoutlines)
        raise CommandFailedException(command, proc.returncode)


def cmd_system(command):
    logging.debug(command)
    exit_code = os.system(command)
    if exit_code != 0:
        raise CommandFailedException(command, exit_code)


def disable_dangerous_stuff():
    dbname = os.environ['PGDATABASE']
    cmd("psql -d %s -c 'DELETE FROM ir_mail_server'" % dbname)
    cmd("psql -d %s -c 'UPDATE fetchmail_server SET active = FALSE'" % dbname)
    cmd("psql -d %s -c 'UPDATE ir_cron SET active = FALSE'" % dbname)
    cmd("psql -d %s -c \"UPDATE ir_config_parameter SET value = 'http://localhost:8069' WHERE key = 'web.base.url'\"" % dbname)


def find_db_version_from_progress():
    global params, progress
    highest_version = params['start-version']
    for version, values in progress.items():
        if float(version) - float(highest_version) > 0.001:
            if 'upgrade' in values and values['upgrade'] or \
               'enterprise' in values and values['enterprise']:
                highest_version = version
    return highest_version


def http_download(url):
    logging.debug('Downloading %s...' % url)
    with urlopen(url) as stream:
        response = stream.read()
        encoding = stream.headers.get_content_charset('utf-8')
        return response.decode(encoding)


def init_progress(version):
    global progress
    if not version in progress:
        progress[version] = {
            'hooks': {}
        }
    elif not 'hooks' in progress[version]:
        progress[version]['hooks'] = {}


def load_defaults(params):
    enterprise_enabled = 'MIGRATION_ENTERPRISE_ENABLED' in os.environ and \
        os.environ['MIGRATION_ENTERPRISE_ENABLED'].lower() in (
            '1',
            'yes',
            'true'
        )
    start_version = os.environ['MIGRATION_START_VERSION'] \
        if 'MIGRATION_START_VERSION' in os.environ else None
    return {**{
        'enterprise-enabled': enterprise_enabled,
        'start-version': start_version,
        'help': False,
        'rebuild': False,
        'reset-progress': False,
        'restore': False,
        'verbose': False,
        'enterprise-dont-resume': False,
        'enterprise-autotrust-ssh': False,
    }, **params}


def load_enterprise_script():
    global params, enterprise_script_filepath

    def alter_code_block(prefix, postfix, replacement):
        i = code.find(prefix) + len(prefix)
        i = code.find("\n", i + 1) + 1
        j = code.find(postfix, i)
        j = code.find("\n", j + 1) + 1
        return code[:i] + replacement + '\n' + code[j:]

    code = http_download('https://upgrade.odoo.com/upgrade')

    # Replace the function body of get_upgraded_db_name
    start = "def get_upgraded_db_name(dbname, target, aim):"
    end = "\n    return"
    code = alter_code_block(
        start,
        end,
        "    return dbname + '-' + target + '-enterprise'"
    )

    # Replace the line that determines the logfile
    code = code.replace(
        "logging.basicConfig(",
        "logging.basicConfig(\n"
        "        filename=\""+WAFT_DIR+"/logfile/%s-%s-enterprise.log\""
                 " % (args.dbname, args.target),\n"
    )

    # Change SSH settings
    if params['enterprise-autotrust-ssh']:
        code = code.replace(
            "-o IdentitiesOnly=yes",
            "-o IdentitiesOnly=yes " +
            "-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null")
    else:
        known_hosts_filepath = os.path.join(MIGRATION_PATH, '.ssh-known-hosts')
        code = code.replace(
            "-o IdentitiesOnly=yes",
            "-o IdentitiesOnly=yes " +
            "-o \\\"UserKnownHostsFile=%s\\\"" % known_hosts_filepath)

    # Write the file away and remember its path
    _, enterprise_script_filepath = mkstemp('-enterprise-upgrade.py')
    with open(enterprise_script_filepath, 'w') as file:
        file.write(code)


def load_progress():
    global params

    HOOK_ORDER = [
        ('pre-migration', False, False),
        ('pre-upgrade', False, False),
        ('enterprise/pre-uprade', False, False),
        ('enterprise/post-upgrade', True, False),
        ('pre-openupgrade', True, False),
        ('post-upgrade', True, True),
        ('post-migration', True, True),
    ]

    if not os.path.exists("progress.json"):
        return {}
    with open("progress.json", "r") as file:
        progress = json.load(file)
    
    # Remove the parts that are not necessary anymore
    if params['reset-progress']:
        if len(params['reset-progress']) > 1:
            version, hook = params['reset-progress']
        else:
            version = params['reset-progress'][0]
            hook = 'post-upgrade'
        i = [x[0] for x in HOOK_ORDER].index(hook)
        for j in range(i, len(HOOK_ORDER)):
            delete_hook, enterprise_done, upgrade_done = HOOK_ORDER[j]
            if version in progress and \
                delete_hook in progress[version]['hook']:
                del progress[version]['hook'][delete_hook]
                if not enterprise_done and 'enterprise' in progress[version]:
                    del progress[version]['enterprise']
                if not upgrade_done and 'upgrade' in progress[version]:
                    del progress[version]['upgrade']
        
        # Also, delete all higher versions from the progress dict
        version = params['reset-progress'][0]
        for v in [k for k in progress.keys()]:
            if float(v) > float(version):
                del progress[v]
    
    return progress


def mark_enterprise_done(version):
    if not version in progress:
        progress[version] = {
            'hooks': {}
        }
    progress[version]['enterprise'] = True
    save_progress()

def mark_upgrade_done(version):
    if not version in progress:
        progress[version] = {
            'hooks': {}
        }
    progress[version]['upgrade'] = True
    save_progress()


def mark_script_executed(version, hook_name, script_path):
    global progress
    if version in progress and \
       'hooks' in progress[version] and \
       hook_name in progress[version]['hooks']:
        if script_path in progress[version]['hooks'][hook_name]:
            return False
    else:
        if version in progress and 'hooks' in progress[version]:
            progress[version]['hooks'][hook_name] = []
        else:
            progress[version] = {
                'hooks': {
                    hook_name: []
                }
            }
    progress[version]['hooks'][hook_name].append(script_path)
    save_progress()
    return True


def parse_arguments():
    arguments = {}

    try:
        optlist, args = getopt.getopt(sys.argv[1:], 'd:ef:hrsv', [
            'database=', 'enterprise-enabled', 'start-version=', 'help',
            'rebuild', 'reset-progress=', 'restore', 'verbose', 'enterprise-dont-resume',
            'enterprise-autotrust-ssh'
        ])
    except getopt.GetoptError as err:
        print(err)
        return

    for opt in optlist:
        arg, value = opt
        
        if arg == '-d' or arg == '--database':
            arguments['database'] = value
        if arg == '-e' or arg == '--enterprise-enabled':
            arguments['enterprise-enabled'] = True
        if arg == '-f' or arg == '--start-version':
            arguments['start-version'] = value
        if arg == '-h' or arg == '--help':
            arguments['help'] = True
        if arg == '-r' or arg == '--rebuild':
            arguments['rebuild'] = True
        if arg == '--reset-progress':
            arguments['reset-progress'] = value.split(':')[:2]
        if arg == '-s' or arg == '--restore':
            arguments['restore'] = True
        if arg == '-v' or arg == '--verbose':
            arguments['verbose'] = True
        if arg == '--enterprise-dont-resume':
            arguments['enterprise-dont-resume'] = True
        if arg == '--enterprise-autotrust-ssh':
            arguments['enterprise-autotrust-ssh'] = True
    return arguments


def pull_customer_database():
    global params
    customer_container = params['customer-container']
    customer_database_name = params['customer-database-name']

    _, tmp_file = mkstemp("-" + customer_database_name + ".sql")
    logging.info("Dumping customer database...")
    cmd([
        "ssh",
        customer_container,
        '/usr/bin/pg_dump -O -x %s > /tmp/%s.sql' % (
            customer_database_name,
            customer_database_name,
        ),
    ])
    logging.info("Downloading customer database...")
    cmd(["scp", "%s:/tmp/%s.sql" % (customer_container, customer_database_name), tmp_file])

    logging.info("Importing customer database...")
    try:
        cmd(["dropdb", os.environ['PGDATABASE']])
    except CommandFailedException:
        pass
    cmd(["createdb", os.environ['PGDATABASE']])
    cmd_system("psql -d \"" + os.environ['PGDATABASE'] + "\" < " + tmp_file)
    logging.info("Customer database import succeeded.")


def prepare():
    # Make sure the migration logfile already exists
    log_path = os.path.join(WAFT_DIR, 'logfile')
    if not os.path.exists(log_path):
        os.mkdir(log_path)
    open(os.path.join(WAFT_DIR, 'logfile/migration.log'), 'a').close()

    # Make sure the migration dir exists
    if not os.path.exists(MIGRATION_PATH):
        os.mkdir(MIGRATION_PATH)


def run_python_script(build_dir, script_path):
    """Execute the given python script in the shell.
    """

    session_unopened = script_path.endswith('-unop.py')

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
""" % (MIGRATION_PATH, build_dir, build_dir)

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
""" % (script_path)

    if not session_unopened:
        header += """
__session.cr.commit()
__session.cr.close()
"""

    exec_path = os.path.join(build_dir, '.venv/bin/python')
    return cmd(exec_path, header)


def rebuild_sources():
    global params
    if not os.path.exists(MIGRATION_PATH):
        os.mkdir(MIGRATION_PATH)
        shutil.copytree(
            os.path.join(WAFT_DIR, 'waftlib/migration'),
            MIGRATION_PATH
        )
    
    def write_env_secret(build_dir, version):
        with open(os.path.join(build_dir, '.env-secret'), 'wt') as file:
            file.write('ODOO_VERSION="%s"\n' % version)
            file.write('PGDATABASE="%s"\n' % os.environ['PGDATABASE'])
            file.write('DBFILTER="^%s$"\n' % os.environ['PGDATABASE'])
            if 'PGPASSWORD' in os.environ:
                file.write('PGPASSWORD="%s"\n' % os.environ['PGPASSWORD'])
            file.write('LOG_LEVEL="DEBUG"\n')
            if params['enterprise-enabled']:
                file.write('DEFAULT_REPO_PATTERN_ODOO="https://github.com/odoo/odoo.git"')
            elif float(version) < 14.0 and version != params['start-version']:
                file.write('DEFAULT_REPO_PATTERN_ODOO="https://github.com/OCA/OpenUpgrade.git"')
    
    versions = available_build_versions(params['start-version'])
    for version in versions:
        build_dir = os.path.join(MIGRATION_PATH, 'build-' + version)
        if float(version) > 13.999 and version == os.environ['ODOO_VERSION']:
            build_dir = WAFT_DIR
        
        # Set up git in build dir
        cmd("mkdir -p \"%s\"" % build_dir)
        cmd("git init", cwd=build_dir)
        try:
            cmd("git remote add sunflowerit https://github.com/sunflowerit/waft.git", cwd=build_dir)
        except:
            pass
        #cmd("git pull --rebase sunflowerit master", cwd=build_dir)

        logging.info("Rebuilding build-%s..." % version)

        # Setup the build dir and bootstrap
        write_env_secret(build_dir, version)
        if build_dir != WAFT_DIR:
            cmd_system(os.path.join(build_dir, 'bootstrap'))
        
        #combine_repos(build_dir, version)
        cmd_system(os.path.join(build_dir, 'build'))
        cmd_system(os.path.join(build_dir, '.venv/bin/pip') +
            ' install ' +
            os.path.join(WAFT_DIR, 'waftlib/migration/api')
        )
        cmd_system(os.path.join(build_dir, '.venv/bin/pip') +
            ' install ' +
            'git+https://github.com/anybox/anybox.recipe.odoo#egg=anybox.recipe.odoo'
        )
        cmd_system(os.path.join(build_dir, '.venv/bin/pip') +
            ' install ' +
            'git+https://github.com/OCA/openupgradelib'
        )
        
        # Change the config
        time.sleep(1)
        cmd_system("sed -i '/logfile =/d' \"" + build_dir + "/auto/odoo.conf\"")
        logfile_path = WAFT_DIR + \
                       "/logfile/" + \
                       os.environ['PGDATABASE'] + '-' + version + '.log'
        cmd_system("echo logfile = \"" + logfile_path + "\" >> \"" + build_dir + "/auto/odoo.conf\"")
        if float(version) < 8.999:
            cmd_system("sed -i '/db_port =/d' \"" + build_dir + "/auto/odoo.conf\"")
            cmd_system("echo \"db_port = 5432\"")
        if float(version) >= 13.999:
            cmd_system("sed -i '/upgrade_path =/d' \"" + build_dir + "/auto/odoo.conf\"")
            cmd_system("sed -i '/server_wide_modules =/d' \"" + build_dir + "/auto/odoo.conf\"")
            cmd_system("echo upgrade_path =  \"" + build_dir + "/custom/src/openupgrade/openupgrade_scripts/scripts\" >> \"" + build_dir + "/auto/odoo.conf\"")
            cmd_system("echo server_wide_modules =  \"openupgrade_framework\" >> \"" + build_dir + "/auto/odoo.conf\"")
        if float(version) <= 10.001:
            cmd_system("echo \"running_env = dev\" >> \"" + build_dir + "/auto/odoo.conf\"")


def run_enterprise_upgrade(version):
    global params, enterprise_script_filepath
    logging.info("Running enterprise upgrade to %s..." % version)

    def read_last_line(file):
        last_line = None
        for line in file:
            if line:
                last_line = line
            logging.info(line.decode('utf-8'))
        return last_line

    def check_process_status(proc):
        if proc.poll() == None:
            return False
        else:
            if proc.returncode != 0:
                if proc.returncode == 1:
                    last_line = read_last_line(proc.stderr).decode('utf-8')
                    if last_line.find("<urlopen error timed out>") != -1:
                        raise TimeoutError()
                    raise Exception("Enterprise upgrade failed with exit code " + str(proc.returncode))
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

    enterprise_database = os.environ['PGDATABASE'] + '-' + version + '-enterprise'
    enterprise_filestore = os.path.join(
        os.environ['HOME'],
        '.local/share/Odoo/filestore/',
        enterprise_database
    )
    try:
        cmd_system('dropdb ' + enterprise_database + ' 2>/dev/null')
    except CommandFailedException:
        pass
    cmd('rm -rf ' + enterprise_filestore)

    log_filepath = os.path.join(
        WAFT_DIR,
        'logfile',
        os.environ['PGDATABASE'] + '-' + version + '-enterprise.log'
    )
    cmd_system('touch "' + log_filepath + '"')
    answer = 'n' if 'enterprise-dont-resume' in params and params['enterprise-dont-resume'] else 'Y'
    done = False
    attempts = 0
    logfile = open(log_filepath, 'r')
    logfile.seek(0, io.SEEK_END)
    #tty = open('/dev/tty', 'r')
    
    while not done:
        if attempts == 10:
            raise Exception("Enterprise upgrade failed, too many attempts.")
        attempts += 1

        try:
            proc = subprocess.Popen([
                'python3',
                enterprise_script_filepath,
                'test',
                '-d',
                os.environ['PGDATABASE'],
                '-t',
                version
            ], stdin=subprocess.PIPE, stderr=subprocess.PIPE)

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
                elif line.find("This upgrade request seems to have been "
                            "interrupted. Do you want to resume it ? "
                            "[Y/n]") != -1:
                    if answer == 'Y':
                        logging.info("Resuming enterprise upgrade request...")
                    else:
                        logging.info("Restarting enterprise upgrade request...")
                    proc.stdin.write((answer + '\n').encode('utf-8'))
                    proc.stdin.flush()
                    answer = 'Y'
        finally:
            proc.kill()
    
    copy_database(enterprise_database, os.environ['PGDATABASE'])


def run_migration(start_version, target_version):
    global params, db_version, progress

    start_version = db_version = params['start-version']
    will_jump = params['enterprise-enabled'] and (float(start_version) + 1.0) < float(ENTERPRISE_MINIMUM_TARGET)
    from_start = False

    if params['enterprise-enabled']:
        load_enterprise_script()

    init_progress(start_version)
    progress_version = find_db_version_from_progress()
    from_start = abs(float(progress_version) - float(db_version)) < 0.001 and (
        not ENTERPRISE_MINIMUM_TARGET in progress or (
            not 'upgrade' in progress[ENTERPRISE_MINIMUM_TARGET] or \
            not progress[ENTERPRISE_MINIMUM_TARGET]['upgrade']
        ) and (
            not 'enterprise' in progress[ENTERPRISE_MINIMUM_TARGET] or \
            not progress[ENTERPRISE_MINIMUM_TARGET]['enterprise']
        )
    )
    
    logging.info("Disabling dangerous stuff...")
    disable_dangerous_stuff()

    if from_start:
        if not start_version in progress or not 'upgrade' in progress[start_version] or not progress[start_version]['upgrade']:
            logging.info("Running initial upgrade...")
            run_upgrade(start_version)
            mark_upgrade_done(start_version)
    else:
        db_version = progress_version
    if float(progress_version) - float(params['start-version']) < 0.001:
        run_scripts(progress_version, 'pre-migration')

    # Running an enterprise migration from the start, may require a 'jump'
    if params['enterprise-enabled']:
        if from_start and (not start_version in progress or \
           not ('enterprise' in progress[start_version] and progress[start_version]['enterprise'])):
            run_scripts(start_version, 'enterprise/pre-migration')
            if will_jump:
                enterprise_done = \
                    ENTERPRISE_MINIMUM_TARGET in progress and \
                    'enterprise' in progress[ENTERPRISE_MINIMUM_TARGET] and \
                    progress[ENTERPRISE_MINIMUM_TARGET]['enterprise']
                openupgrade_done = \
                    ENTERPRISE_MINIMUM_TARGET in progress and \
                    'upgrade' in progress[ENTERPRISE_MINIMUM_TARGET] and \
                    progress[ENTERPRISE_MINIMUM_TARGET]['upgrade']
                if not enterprise_done:
                    run_scripts(start_version, "pre-upgrade")
                    run_scripts(start_version, "enterprise/pre-upgrade")
                    run_scripts(ENTERPRISE_MINIMUM_TARGET, "enterprise/pre-jump", start_version)
                    run_enterprise_upgrade(ENTERPRISE_MINIMUM_TARGET)
                    mark_enterprise_done(ENTERPRISE_MINIMUM_TARGET)
                db_version = ENTERPRISE_MINIMUM_TARGET
                if not openupgrade_done:
                    run_scripts(ENTERPRISE_MINIMUM_TARGET, "enterprise/post-jump")
                    run_scripts(ENTERPRISE_MINIMUM_TARGET, "enterprise/post-upgrade")
                    run_scripts(ENTERPRISE_MINIMUM_TARGET, "post-upgrade")
        elif abs(float(progress_version) - float(ENTERPRISE_MINIMUM_TARGET)) < 0.001:
            db_version = ENTERPRISE_MINIMUM_TARGET
            run_scripts(ENTERPRISE_MINIMUM_TARGET, "enterprise/post-jump")
            run_scripts(ENTERPRISE_MINIMUM_TARGET, "enterprise/post-upgrade")
            run_scripts(ENTERPRISE_MINIMUM_TARGET, "post-upgrade")

    # If not running from the start, we may need to call the
    # the post-upgrade scripts of the previous version.
    for version in available_build_versions(start_version):
        if version == start_version or float(db_version) - float(version) > 0.999 or (
            params['enterprise-enabled'] and \
            not version in available_enterprise_build_versions(start_version)
        ):
            continue
        enterprise_done, openupgrade_done = (False, False)
        if version in progress:
            if 'enterprise' in progress[version]:
                enterprise_done = progress[version]['enterprise']
            if 'upgrade' in progress[version]:
                openupgrade_done = progress[version]['upgrade']
        if enterprise_done or openupgrade_done:
            db_version = version
        
        init_progress(version)
        if not enterprise_done and not openupgrade_done:
            run_scripts(version, "pre-upgrade")
        if params['enterprise-enabled']:
            if not enterprise_done and \
               float(version) - float(ENTERPRISE_MINIMUM_TARGET) > 0.001:
                run_scripts(version, "enterprise/pre-upgrade")
                run_enterprise_upgrade(version)
                db_version = version
                mark_enterprise_done(version)
                if not openupgrade_done:
                    run_scripts(version, "enterprise/post-upgrade")
        if not openupgrade_done:
            run_scripts(version, "pre-openupgrade")
            logging.info("Running OpenUpgrade to %s..." % version)
            run_upgrade(version)
            mark_upgrade_done(version)
        db_version = version
        run_scripts(version, "post-upgrade")
    
    if params['enterprise-enabled']:
        run_scripts(db_version, "enterprise/post-migration")
    run_scripts(db_version, "post-migration")


def run_script(script_path):
    global config, db_version
    final_version = os.environ['ODOO_VERSION']
    logging.info("Running script %s..." % script_path)

    if script_path.endswith('.py'):
        build_dir = WAFT_DIR if db_version == final_version and float(db_version) > 13.999 \
            else MIGRATION_PATH + '/build-' + db_version
        run_python_script(build_dir, script_path)
    elif script_path.endswith('.sh'):
        cmd(['bash', script_path])
    elif script_path.endswith('.sql'):
        script_content = "\\set ON_ERROR_STOP true\n" + \
                            open(script_path, 'r').read()
        cmd('psql -d ' + os.environ['PGDATABASE'], script_content)
    elif script_path.endswith('.link'):
        actual_subpath = open(script_path).readline().strip()
        actual_script_path = MIGRATION_PATH + '/hook/common/' + actual_subpath
        if os.path.exists(actual_script_path):
            return run_script(actual_script_path)
        actual_script_path = WAFT_DIR + '/waftlib/migration/hook/common/' + actual_subpath
        if os.path.exists(actual_script_path):
            return run_script(actual_script_path)
        raise Exception("Script \"%s\" not found" % actual_subpath)
    else:
        return False
    return True



def run_scripts(version, hook_name, from_version=None):
    global config, progress

    logging.info("Loading %s %s scripts..." % (version, hook_name))

    def listdir_full_paths(path):
        if not os.path.exists(path):
            return []
        return [
            (filename, os.path.join(path, filename))
            for filename in os.listdir(path)
        ]

    scripts_path1 = os.path.join(WAFT_DIR, 'waftlib/migration/hook', hook_name)
    scripts_path2 = os.path.join(MIGRATION_PATH, 'hook', hook_name)
    scripts_path3 = os.path.join(WAFT_DIR, 'build-' + version, 'hook', hook_name)
    scripts_path4 = os.path.join(MIGRATION_PATH, 'waftlib/migration/build-' + version, 'hook', hook_name)
    scripts = listdir_full_paths(scripts_path1) + \
              listdir_full_paths(scripts_path2) + \
              listdir_full_paths(scripts_path3) + \
              listdir_full_paths(scripts_path4)

    for script_filename, script_path in sorted(scripts, key=lambda x: x[0]):
        if version in progress and \
           'hooks' in progress[version] and \
           hook_name in progress[version]['hooks'] and \
           script_path in progress[version]['hooks'][hook_name]:
            continue
        if not check_script_support(script_path, version, from_version):
            continue

        if not run_script(script_path):
            logging.error("Unknown file extension for script " + script_filename +
                  ", skipping...")
            continue

        mark_script_executed(version, hook_name, script_path)


def run_upgrade(version):
    instance = os.environ['PGDATABASE'] + "-" + version
    final_version = os.environ['ODOO_VERSION']
    build_dir = WAFT_DIR if version == final_version and float(version) >= 14.0 \
        else MIGRATION_PATH + '/build-' + version

    logfile = os.path.join(WAFT_DIR, 'logfile', instance + '.log')
    args = '-u all --stop-after-init --logfile "%s"' % logfile
    cmd(build_dir + '/run ' + args)
    copy_database(os.environ['PGDATABASE'], instance)


def save_progress():
    global progress
    with open("progress.json", "w") as file:
        json.dump(progress, file, indent=2)


def setup_logging():
    log_filepath = os.path.join(WAFT_DIR, 'logfile/migration.log')
    log_level = os.environ['WAFT_LOG_LEVEL']
    log_file_handler = logging.FileHandler(log_filepath)
    log_file_handler.setLevel(logging.DEBUG)
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(log_level)
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            log_file_handler,
            stream_handler
        ]
    )


def verify_arguments(args: dict):
    return True

def verify_params():
    global params
    if not 'PGDATABASE' in os.environ or not os.environ['PGDATABASE']:
        logging.error("No database specified in the environment as PGDATABASE.")
        return False
    if not 'start-version' in params or not params['start-version']:
        logging.error("No start version specified. Use either --start-version on the command line, or MIGRATION_START_VERSION in the environment.")
        return False
    return True


def main():
    global params, progress
    
    try:
        args = parse_arguments()
        if args == None or not verify_arguments(args):
            return 1
        
        if 'help' in args:
            print(HELP_TEXT)
            return 0
        
        prepare()
        params = load_defaults(args)
        if not verify_params():
            return 1
        setup_logging()
        
        if params['rebuild']:
            logging.info("Rebuilding sources...")
            rebuild_sources()
        
        progress = load_progress()
        logging.debug('Loaded progress: ' + str(progress))

        if params['restore']:
            if progress:
                logging.error("You have chosen to restore from the customer database, but there is still progress saved.")
                logging.error("To restore the customer database, remove the progress.json file.")
                return
            else:
                pull_customer_database()

        start_version = params['reset-progress'][0] if params['reset-progress'] else params['start-version']
        target_version = os.environ["ODOO_VERSION"]
        logging.info("Starting migration from %s to %s...", start_version, target_version)
        run_migration(start_version, target_version)
        logging.info("Migration completed.")
    except Exception as e:
        _, name, tb = sys.exc_info()
        stacktrace = traceback.format_tb(tb)
        logging.error("Error occurred: %s\nStacktrace:\n%s" % (e, ''.join(stacktrace)))
        exit(1)


main()
