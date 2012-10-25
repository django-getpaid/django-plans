#!/usr/bin/env python2
# -*- coding: utf-8 -*-
from setuptools import find_packages, setup

with open('README.rst') as file:
    long_description = file.read()

setup(
    name='django-plans',
    version='0.1',
    description='Pluggable django app for managing pricing plans with quotas and accounts expiration',
    long_description=long_description,
    author='Krzysztof Dorosz',
    author_email='cypreess@gmail.com',
    url='https://github.com/cypreess/django-plans',
    license='MIT',

    packages=find_packages(),
    classifiers=[
        'Development Status :: 4 - Beta',
        'Framework :: Django',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
    ],
    install_requires=['django', 'vatnumber'],
    dependency_links=['git://github.com/sbrandtb/django-ordered-model.git',
                      'git://github.com/bearstech/django-transmeta.git',
                      'git://github.com/bradleyayers/suds-htj.git'],
    include_package_data=True,
    zip_safe=False,
)
