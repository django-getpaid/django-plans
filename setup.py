#!/usr/bin/env python2
# -*- coding: utf-8 -*-
from setuptools import find_packages, setup

with open('README.rst') as file:
    long_description = file.read()

setup(
    name='django-plans',
    version='0.6.1',
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
    install_requires=[
        'django-countries>=2.0',
        'pytz',
        'django-ordered-model',
        'vatnumber',
        'celery',
    ],
    extras_require={
        'i18n': [
            'django-modeltranslation>=0.5b1',
        ],
    },
    dependency_links=[
        'https://github.com/htj/suds-htj/downloads'
    ],
    include_package_data=True,
    zip_safe=False,
)
