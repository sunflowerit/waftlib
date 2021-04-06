import setuptools

setuptools.setup(
    name="SFOIL",
    version="0.1",
    install_requires=[],
    classifiers=[
        "Development Status :: 3 - Alpha",
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'Topic :: Software Development :: Build Tools',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
    scripts=[
        "bin/sfoil-bootstrap",
        "bin/sfoil-create-venv",
        "bin/sfoil-build",
        "bin/sfoil-check-project",
        "bin/sfoil-check-requirements",
    ],
)

