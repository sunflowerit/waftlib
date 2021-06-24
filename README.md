# Waft Odoo installation method

Waft is a wrapper for installing [Odoo](https://github.com/odoo/odoo).

In this, it is similar to:

- The [Anybox buildout recipe](https://github.com/anybox/anybox.recipe.odoo), yet instead of relying on the aging [buildout](https://github.com/buildout/buildout) tool, it relies on [pip](https://github.com/pypa/pip) to install Python modules and [git-aggregator](https://github.com/acsone/git-aggregator) for Odoo module branch aggregation.

- [Doodba](https://github.com/tecnativa/doodba), yet instead of using Docker, it runs native on your Linux system and keeps all relevant files in one folder.

In fact, many scripts are borrowed from Doodba.

## Why?

We needed a tool that could replace buildout, but did not want to switch to a Docker development workflow.

## What does it do

- Install Python dependencies in a virtual environment
- Collect Odoo modules from different Git repositories (repos.yaml)
- Select some modules and not others (addons.yaml)
- Generate the Odoo config file
- Offer some handy scripts to do things

## What it does not do

- Install postgres
- Install lessc
- Install wkhtmltopdf
- Install pipenv
- Install system requirements for compiling the necessary Python modules (lxml, yaml etc)

You'll need to take care of these yourself.

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

```
vi common/conf.d/odoo.conf  # Odoo config file template. You can use ENVIRONMENT variables here.
vi .env-shared              # Shared defaults that apply for all clones of this instance
vi .env-secret              # local overrides such as DBFILTER, PGDATABASE, PGUSER etc
vi custom/src/repos.yaml    # https://github.com/Tecnativa/doodba#optodoocustomsrcreposyaml
vi custom/sec/addons.yaml   # https://github.com/Tecnativa/doodba#optodoocustomsrcaddonsyaml
./build
```

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
pipenv install --keep-outdated mypythonpackagename
# Then commit and push to share the new Pipfile with colleagues
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
./pipenv run click-odoo -c ./auto/odoo.conf my-script.sh
```

To run any other custom Odoo command:

```
./pipenv run odoo -c auto/odoo.conf --help
```

## What if I still want to use Docker?

You can! Just define a `Dockerfile` at the root of your project and do all things you need to do to get a working OS that supports Waft. For example: use `Ubuntu 20.04` base image, install `npm`, `lessc`, `libpython-dev`, `wkhtmltopdf`, `Postgres`, `pipenv`, run `./bootstrap`, `./build`, `./run`.

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

You Can also set up a dev environment with pycharm.
This allows you to develop locally if you wish to. Firstly:
 - Follow the setup step steps and make sure your
   odoo environment is ready.
     
 - Install latest pycharm.

 Once the above steps are set, then do the following
 under pycharm:

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
   choose the *odoo.py* file. This is like *odoo-bin.py/openerp.py* 
   in odoo folders.
   
    **NB: You can add a shell script that has all options including 
    parameters.** 
   
   
 - Add odoo parameters if any e.g `-c odoo-config-path/odoo.conf --workers=0` etc.

 
- Lastly and importantly, add the existing virtual env under 
  *python interpreter*, that you had earlier configured in 
  the first step, and run.

  
