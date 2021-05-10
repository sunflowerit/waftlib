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
- Collect Odoo modules from different Git repositories
- Select some modules and not others
- Generate the Odoo config file

## What it does not do

- Install postgres
- Install lessc
- Install wkhtmltopdf
- Install pipenv and pyenv
- Install system requirements for compiling the necessary Python modules (lxml, yaml etc)

You'll need to take care of these yourself.

## Usage

Clone the [waft template project](https://github.com/sunflowerit/waft) and run bootstrap:

    git clone https://github.com/sunflowerit/waft
    ./bootstrap

It will clone waftlib and exit with a suggestion to do more things, which we will do now.

Select an Odoo version that you want to use, for example 13.0

Copy templates and rerun bootstrap:

```
cp waftlib/templates/13.0/.env-shared .
cp waftlib/templates/13.0/Pipfile .
./bootstrap
```

When successful, now we can prepare for building Odoo:

```
cp .env-shared .env-local  # override some vars such as DBFILTER, PGDATABASE, PGUSER etc
./build
```

Now we can create database and run Odoo:

```
./install mydatabase web
./run
```
