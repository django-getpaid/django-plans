#!/usr/bin/env python2
# -*- coding: utf-8 -*-
from distutils.core import setup
 
setup(
    name='django-plans',
    version='0.1',
    description='Allows Django accounts to have plans with expirations and parameters.',
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
)