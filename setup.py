#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import find_packages, setup

from plans import __version__ as VERSION

with open("README.rst") as file:
    long_description = file.read()

setup(
    name="django-plans",
    version=VERSION,
    description="Pluggable django app for managing pricing plans with quotas and accounts expiration",
    long_description=long_description,
    author="Krzysztof Dorosz",
    author_email="cypreess@gmail.com",
    url="https://github.com/django-getpaid/django-plans",
    license="MIT",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Framework :: Django",
        "Framework :: Django :: 4.2",
        "Framework :: Django :: 5.0",
        "Framework :: Django :: 5.1",
        "Framework :: Django :: 5.2",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
    ],
    install_requires=[
        "django-countries>=4.5",
        "pytz>=2017.2",
        "django-ordered-model>=1.4.1",
        "python-stdnum",
        "django-next-url-mixin>=0.1.0",
        "zeep",
        "django-sequences",
        "swapper~=1.3.0",
        "six",
    ],
    extras_require={
        "i18n": [
            "django-modeltranslation>=0.5b1",
        ],
    },
    include_package_data=True,
    zip_safe=False,
)
