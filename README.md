# Waft Odoo installation method

Waft is a wrapper for installing [Odoo](https://github.com/odoo/odoo).

In this, it is similar to:

- The [Anybox buildout recipe](https://github.com/anybox/anybox.recipe.odoo), yet instead of relying on the aging [buildout](https://github.com/buildout/buildout) tool, it relies on [pip](https://github.com/pypa/pip) to install Python modules and [git-aggregator](https://github.com/acsone/git-aggregator) for Odoo module branch aggregation.

- [Doodba](https://github.com/tecnativa/doodba), yet instead of using Docker, it runs native on your Linux system and keeps all relevant files in one folder.

In fact, many scripts are borrowed from Doodba.

## Why?

We needed a tool that could replace buildout, but did not want to switch to a Docker development workflow.

## What does it do

- Install the Python version in `.python-version` using `pyenv`
- Install Python dependencies from `requirements.txt` in a virtual environment in `.venv`
- Use `gitaggregrator` to collect Odoo modules from different `git` repositories and branches as defined in `repos.yaml` in `custom/src/XXX/YYY` folders
- Select some modules and not others (addons.yaml)
- Generate the Odoo config file in `auto/odoo.conf`
- Offer some handy scripts to do things: `./upgrade`, `./install`, `./shell`, `waftlib/bin/reset-password`, ...

## What it does not do (or: prerequisites)

- Install postgres
- Install lessc
- Install wkhtmltopdf
- Install system requirements for compiling the necessary Python modules (lxml, yaml etc)

You'll need to take care of these yourself.

As for the system requirements, take a look at the files in [this folder](https://github.com/sunflowerit/waftlib/tree/master/templates) or also checkout the [pyenv prerequisites](https://github.com/pyenv/pyenv/wiki#suggested-build-environment)

Note: when you do want to use an existing python version or system python, you can create a
virtual environment in the root directory by using `$ python -m venv .venv` or
if you have an existing virtualenv binary: `$ virtualenv .venv.

## Setup a waft project

Clone the [waft template project](https://github.com/sunflowerit/waft) and run bootstrap:

    git clone https://github.com/sunflowerit/waft
    cd waft && ./bootstrap

It will clone waftlib and exit with a suggestion to do more things, which we will do now.

Select an Odoo version that you want to use, for example 13.0

Create your secret environment variables file from default environment variables template file and rerun bootstrap:

```
cp waftlib/templates/13.0/.env-shared .env-secret
./bootstrap
```

When successful, now we can prepare for building Odoo:
- Take a look at default odoo config file `vi common/conf.d/odoo.conf`.
- Override odoo config variables as you like `vi common/conf.d/override-odoo.conf`. You can use ENVIRONMENT variables here
- Take a look at defaults shared variables `vi .env-shared` that apply for all clones of this instance, you can replace the link to templet file with a regular file and modify it as you like. NOTE: don't put secret variables values in this file.
- You can override variables in `.env-shared` by putting it in `.env-secret` such as DBFILTER, PGDATABASE, PGUSER etc
- Take a look at default [`custom/src/repos.yaml`](https://github.com/Tecnativa/doodba#optodoocustomsrcreposyaml), if you like to modify it replace the link with a regular file.
- Take a look at default [`custom/sec/addons.yaml`](https://github.com/Tecnativa/doodba#optodoocustomsrcaddonsyaml), if you like to modify it replace the link with a regular file.
- Issue build script `./build`

Now we can create database and run Odoo:

```
./install mydatabase web
./run
```

At this point when you know the project configuration is complete, you can push it back to Git, but not to the `waft` repository, but to your project's repository, for example to a branch named `build`:

```
git rm -Rf .git
git init
git add .
git commit -a "[ADD] Initial project commit"
git checkout -b build
git remote add origin git@github.com/mycompany/myproject
git push --set-upstream origin build
```

Now everyone who wants to work with your project can:

- Clone it
- Edit `.env-secret` to match their local environment (Postgres connection details, etc)
- Run `./bootstrap` and `./build`, and get going.

## Usage

To add a new Python module:

```
# edit requirements.txt, add the module you want
./build

OR:

# edit requirements.txt, add the module you want
source .venv/bin/activate
pip install -r requirements.txt

# Then commit and push to share the new requirements.txt with colleagues
```

To add a new Odoo module:

```
vi custom/src/repos.yaml
vi custom/src/addons.yaml
./build
```

To start an Odoo shell:

```
./shell
# Now you get a shell that has `env` object
```

To start a [click-odoo](https://github.com/acsone/click-odoo) script:

```
source .venv/bin/activate
click-odoo -c ./auto/odoo.conf my-script.sh
```

To run any other custom Odoo command:

```
source .venv/bin/activate
odoo -c auto/odoo.conf --help
```

## Upgrade waftlib from `v.21.05.10` to `v.21.09.22` version:

- Stop odoo.
- Open shell in your waft project directory.
- Issue `pipenv run pip freeze > requirements.txt`, you don't need to do that if you didn't modify the default Pipfile.
- Take care about python version, if you don't have the same default python version in `waftlib/templates/13.0/.python-version #for odoo 13.0 in example` you should create a regular `.python-version` file in the main directory with your python version. you don't need to do that if you didn't modify the default Pipfile.
- Remove `Pipfile`.
- Remove `Pipfile.lock`.
- Remove `.venv` directory.
- If you didn't modify the default `.env-shared` remove it.
- If you didn't modify the default `common/conf.d/odoo.cfg` remove it.
- If you didn't modify the default `custom/src/addons.yaml` remove it.
- If you didn't modify the default `custom/src/repos.yaml` remove it.
- Issue `/usr/bin/curl https://raw.githubusercontent.com/sunflowerit/waft/fec170fd456a371b3468b8d9eef505bf079af40c/bootstrap -o bootstrap`
- Issue `/usr/bin/curl https://raw.githubusercontent.com/sunflowerit/waft/fec170fd456a371b3468b8d9eef505bf079af40c/.gitignore -o .gitignore`
- Issue `./bootstrap`
- Issue `./build`
- Start odoo.

## What if I still want to use Docker?

You can! Just define a `Dockerfile` at the root of your project and do all things you need to do to get a working OS that supports Waft. For example: use `Ubuntu 20.04` base image, install `npm`, `lessc`, `libpython-dev`, `wkhtmltopdf`, `Postgres`, run `./bootstrap`, `./build`, `./run`.

## What if I don't like the `waftlib` scripts and I want to override them

You can! All scripts are symlinks pointing into waftlib, and the symlinks are stored in the project's Git. Meaning you can delete them and override them with your own script. Example:

```
git rm ./bootstrap
cp waftlib/bootstrap .
vi bootstrap  # edit like you wish
git add bootstrap
git commit -m "[UPD] use modified Bootstrap script"
```

Note that when you do this, you won't subscribe to Waft updates anymore, so if there is a change or fix in `waftlib/bootstrap`, you will need to update it in your project manually.


## Setting up a Development Environment (PyCharm)

You can also set up a dev environment with Pycharm.
This allows you to develop locally if you wish to. Firstly:
 - Follow the setup steps and make sure your
   odoo environment is ready.
     
 - Install latest PyCharm.

 Once the above steps are set, then do the following
 under Pycharm:

 - Go to your project *settings* (i.e waft folder project) under *File menu* 
   and select *Python Interpreter.*
   
  
 - Click on Add, select existing environment, this is because,
   if you followed the setup steps above, you should have a 
   hidden *.venv* folder under *waft* folder
   
   
 - If you have the hidden *.venv* folder, then select
   *python* under *bin* folder and save the settings, you can
   also make it available for other projects *(option)*.
   

 - Click on The *Add configuration* option, select left *+
   sign* to add python configuration.
   
   
 - Give the python configuration a name, then select **script path** 
   option, and add a script from the hidden *.venv* folder, under *bin*, 
   choose the *odoo* file. This is like *odoo-bin.py/openerp.py* 
   in odoo folders. You can add **run** script to make work easier, it
   is a script that runs odoo instance.
   
   
 - Add odoo parameters if any e.g `-c odoo-config-path/odoo.conf --workers=0` etc.

 
- Lastly and importantly, add the existing virtual env under 
  *python interpreter*, that you had earlier configured in 
  the first step, and run.

## Migrate Odoo

Waft includes a migration script that can be used to migrate an Odoo instance using OpenUpgrade & the enterprise migration script.
[More info here...](doc/MIGRATION.md)
