import os
import sys
from decimal import Decimal

from django.conf import settings

sys.path[:0] = [os.path.join(os.getcwd(), 'demo')]


def pytest_configure(config):
    settings.configure(
        DATABASE_ENGINE='sqlite3',
        DATABASES={
            'default': {
                'NAME': ':memory:',
                'ENGINE': 'django.db.backends.sqlite3',
                'TEST_NAME': ':memory:',
            },
        },
        DATABASE_NAME=':memory:',
        TEST_DATABASE_NAME=':memory:',
        INSTALLED_APPS=[
            'django.contrib.auth',
            'django.contrib.contenttypes',
            'django.contrib.admin',
            'django.contrib.sessions',
            'django.contrib.sites',
            'ordered_model',
            'example.foo',
            'plans',
        ],
        ROOT_URLCONF='example.urls',
        DEBUG=False,
        SITE_ID=1,
        TEMPLATE_DEBUG=True,
        USE_TZ=True,
        ALLOWED_HOSTS=['*'],
        PLANS_INVOICE_ISSUER={
            "issuer_name": "My Company Ltd",
            "issuer_street": "48th Suny street",
            "issuer_zipcode": "111-456",
            "issuer_city": "Django City",
            "issuer_country": "PL",
            "issuer_tax_number": "PL123456789",
        },
        PLANS_TAX=Decimal(23.0),
        PLANS_TAXATION_POLICY='plans.taxation.eu.EUTaxationPolicy',
        PLANS_TAX_COUNTRY='PL',
        PLANS_CURRENCY='PLN',
        PLANS_VALIDATORS={
            'MAX_FOO_COUNT': 'example.foo.validators.max_foos_validator',
        },
        EMAIL_BACKEND='django.core.mail.backends.console.EmailBackend',
    )
