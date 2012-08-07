#!/usr/bin/env python2
# -*- coding: utf-8 -*-
from distutils.core import setup
 
setup(
    name='django-plans',
    version='0.1',
    description='Pluggable django app for managing pricing plans with quotas and accounts expiration',
    author='Krzysztof Dorosz',
    author_email='cypreess@gmail.com',
    url='https://bitbucket.org/cypreess/django-plans',
    packages=[
        'plans',
        'plans.tests',
    ],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Framework :: Django',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
    ],
    install_requires=['django', 'vatnumber', 'django-ordered-model'],
    dependency_links=[  'git://github.com/bearstech/django-transmeta.git#egg=django-transmeta',
                        'git://github.com/bradleyayers/suds-htj.git#egg=suds-htj']
)