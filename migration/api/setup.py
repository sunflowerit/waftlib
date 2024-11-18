from setuptools import setup
import sys


if sys.version_info.major == 2:
    required_packages = ['psycopg2']
else:
    required_packages = ['psycopg']


setup(
    name='migrationapi',
    version='1.0',
    description='Python API for migration scripts',
    author='Therp B.V.',
    packages=['migrationapi'],
    install_requires=required_packages,
    package_dir={
        'migrationapi': '.',
    },
)
