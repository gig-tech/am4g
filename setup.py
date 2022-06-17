#!/usr/bin/python
from setuptools import setup, find_packages
import os
_version="0.0.1"

long_description=""

### IMPORTANT: Example for distributing ansible modules from
#https://github.com/TerryHowe/ansible-modules-hashivault/blob/master/setup.py

files = [ "ansible/modules/am4g"]

setup(
        name='am4g',
        version=_version,
        packages=files,
        scripts=[],
        description='Ansible module for GIG based clouds',
        long_description=long_description,
        long_description_content_type="text/markdown",
        author='Kevin Hunyadi',
        author_email='kevin.hunyadi@gig.tech',
        url='',
        python_requires= ">=2.7.5",
        classifiers=[
                    "License :: Other/Proprietary License",
                    "Operating System :: OS Independent",
                ],
        install_requires=[
                    'ansible>=2.9.0',
                    'pc4g>=1.0.0',
                ],
    )
