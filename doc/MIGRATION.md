# Migration Framework Documentation

## The migration process

Waft's migration framework can be used to migrate the database (& filestore) of an Odoo instance.
The way the migration is performed, differs a bit when enterprise modules are used or not.
Odoo's enterprise modules can only be migrated with the use Odoo's own migration script, rather than the regular update mechanism inside Odoo itself.
All OCA modules are should be upgraded using OpenUpgrade, which is just a regular upgrade of all the Odoo modules, but the openupgradelib Python package should be available.
Now, when both enterprise modules and OCA modules are installed and need to be migrated, this poses a problem.
The reason being, when the enterprise migration script is being invoked, it will generally migrate only the core and enterprise modules, but it does so for multiple Odoo versions at once.
This can leave any OCA or other custom modules un-migrated when the enterprise migration script has finished.
When this happens, what needs to be taken into account is that this may require some manual labor in order to migrate the remaining modules.

So a migration with this migration framwork without enterprise will migrate to one higher major version each time, while the migration with enterprise will generally make an initial jump from the start version to something a bit higher, and only then it will start migrating one major version at the time.
So a non-enterprise migration would look like this:

12.0 -> 13.0 -> 14.0 -> 15.0 -> 16.0

While the enterprise equivalent could look like this:

12.0 -> 15.0 -> 16.0

The first version that will be migrated to (so 15.0 in this example) may change in the future. This is a restriction imposed by the Odoo's own migration script, and we can't do much about it.

## Environment variables
To get started with the migration script, you need to set up a waft build as per usual; the migration scripts are already included in waftlib.
You need to configure the ODOO_VERSION environment variable as per usual, and then set a bunch of other environment variables as well, preferably not just in .env-secret.

Here are the variables that are important for the migration:

* `ODOO_VERSION` - This variable of the waft build should be set to the target odoo version, the version you want to migrate to.
* `MIGRATION_START_VERSION` - The Odoo version of the unmigrated database.
* `MIGRATION_ENTERPRISE_ENABLED` - If set to true, the migration script will use the enterprise scripts of Odoo for the migration of the core, instead of OpenUpgrade.
* `MIGRATION_ENTERPRISE_JUMP_TO` - The first version that the first enterprise upgrade step will upgrade to. More about this later.
* `MIGRATION_OPEN_UPGRADE_DISABLED` - Is set to true, no local upgrades will be performed after each enterprise upgrade, which it usually does do. Only usable when enterprise is enabled, makes no sense otherwise.
* `MIGRATION_NO_BACKUPS` - If set to true, will not make any intermediate database and filestore backups. Will generally speaking save a lot of space.
* `SKIP_INITIAL_UPGRADE` - By default, an upgrade is performed at the first (start) version. If this is set to true, that will be avoided. Sometimes you don't need it, sometimes the initial upgrade may break stuff.

Once you have set the necessary variables, you can continue setting up the build directory.

## Set up the migration folder

One thing first. In order to use the migration script in any way, we need a working Waft build that has already been bootstrapped and build like usual.
Then, you should be able to use the `./migrate -r` command, which will build all the migration folders.
One note though, you might get an error about a old-repos.yaml file.
Put a copy of the original repos.yaml in custom/src/old-repos.yaml .
In most cases, this can simply be copied from the old waft build.
Once you run the `./migrate -r` command again, it should set up and build all the required folders for you.
Any build folder that did not yet exist, will be generated with a repos.yaml file that is based on the old-repos.yaml file.

## CConsiderations when migrating with Enterprise

An issue that arises from invoking the enterprise script multiple times, is that the enterprise script uses a different ssh port every time. However, the ssh tool remembers the server's public key together with the used port. This means that the ssh tool is usually not going to recognize the server's public key, effectively defeating the security that ssh is supposed to bring.
However, this also means that the script needs user input at multiple stages, to accept the key for a new connection point. To make your life easier, you can use the --enterprise-autotrust-ssh flag on the command line.

## Installing and uninstalling modules

It is good practice to uninstall all modules you won't need at the end anymore after the migration, at the beginning of the migration.
This makes the potential for any possible migration errors smaller, if you are ok with losing the data associated with the module.

The migration script will uninstall all modules at the beginning of the migration when its name in listed in `migration/etc/uninstall-modules.txt`.
The same thing goes for installing modules at the end of the migration, those names can be listed in `migration/etc/install-modules.txt`.

## Adding scripts to the migration script

If you need to change something to the database, at any point during the migration, you can place scripts in the migration folder.
There are different 'hooks' that can be used, and they determine when the script in ran.
The hooks go by the following names:
* pre-migration
* pre-jump
* pre-upgrade
* enterprise/pre-upgrade  (only if enterprise is enabled)
* enterprise/post-upgrade (only if enterprise is enabled)
* pre-openupgrade
* post-upgrade
* post-jump
* post-migration


Most of these terms probably make sense. However, the pre-jump and post-jump hooks need some explanation. These hooks are only executed when an enterprise enabled migration is going to happen that needs to migrate the database more than one version in the beginning. They refer to the 'initial jump' that is performed.

## Running the migration

Once everything is properly set up, to actually run the migration, you can simply do so with `./migrate`.
Running the migration script also creates a progress.json file.
This file tracks the progress of the migration, so that if it fails, it should be able to continue from where it left off.
If you want to restart from an earlier 'position', you need to edit that file, but there are command-line flags to do it automatically as well. Like if you want to start again from one of the backed up database again, for example.
If you want to start from the start again, you can just load a new database, and delete the progress.json file.

