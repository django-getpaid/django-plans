# -*- coding: utf-8 -*-
from __future__ import unicode_literals

# Django settings for example project.
import os
from decimal import Decimal

EMAIL_FROM = "Test <test@server.com>"

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SITE_ROOT = os.path.dirname(os.path.realpath(__file__))

DEBUG = True

ADMINS = (
    # ('Your Name', 'your_email@example.com'),
)

ALLOWED_HOSTS = ['*']

MANAGERS = ADMINS

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        # Add 'postgresql_psycopg2', 'postgresql', 'mysql', 'sqlite3' or 'oracle'.
        'NAME': 'postgres',  # Or path to database file if using sqlite3.
        'USER': 'postgres',  # Not used with sqlite3.
        'PASSWORD': 'postgres',  # Not used with sqlite3.
        'HOST': 'localhost',  # Set to empty string for localhost. Not used with sqlite3.
        'PORT': '5432',  # Set to empty string for default. Not used with sqlite3.
    }
}

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}

TIME_ZONE = 'America/Chicago'
USE_TZ = True
LANGUAGE_CODE = 'en'
SITE_ID = 1
USE_I18N = True
USE_L10N = True

LANGUAGES = (
    ('en', 'English'),
)

MEDIA_ROOT = ''
MEDIA_URL = ''
STATIC_ROOT = ''
STATIC_URL = '/static/'
ADMIN_MEDIA_PREFIX = '/static/admin/'
STATICFILES_DIRS = (
    os.path.join(SITE_ROOT, 'static'),
)

STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    #    'django.contrib.staticfiles.finders.DefaultStorageFinder',
)

SECRET_KEY = 'l#^#iad$8$4=dlh74$!xs=3g4jb(&j+y6*ozy&8k1-&d+vruzy'

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            os.path.join(SITE_ROOT, 'templates'),
        ],
        'APP_DIRS': False,
        'OPTIONS': {
            'debug': True,
            'context_processors': [
                'django.contrib.auth.context_processors.auth',
                'django.template.context_processors.debug',
                'django.template.context_processors.i18n',
                'django.template.context_processors.media',
                'django.template.context_processors.static',
                'django.template.context_processors.tz',
                'django.template.context_processors.request',
                'django.contrib.messages.context_processors.messages',
                'plans.context_processors.account_status',
            ],
            'loaders': [
                'django.template.loaders.filesystem.Loader',
                'django.template.loaders.app_directories.Loader',
            ]
        },
    },
]


ROOT_URLCONF = 'example.urls'
WSGI_APPLICATION = 'example.wsgi.application'

DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',

    'ordered_model',
    'bootstrap3',
    'django_concurrent_tests',

    'plans',
    'example.foo',
    'django_extensions',
    'sequences.apps.SequencesConfig',
]

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'mail_admins': {
            'level': 'ERROR',
            'class': 'django.utils.log.AdminEmailHandler'
        },

    },
    'loggers': {
        'django.request': {
            'handlers': ['mail_admins'],
            'level': 'ERROR',
            'propagate': True,
        },

    }
}


# This is required for django-plans

PLANS_INVOICE_ISSUER = {
    "issuer_name": "My Company Ltd",
    "issuer_street": "48th Suny street",
    "issuer_zipcode": "111-456",
    "issuer_city": "Django City",
    "issuer_country": "PL",
    "issuer_tax_number": "PL123456789",
}

PLANS_TAX = Decimal('23.0')
PLANS_TAXATION_POLICY = 'plans.taxation.eu.EUTaxationPolicy'
PLANS_TAX_COUNTRY = 'PL'

PLANS_VALIDATORS = {
    'MAX_FOO_COUNT': 'example.foo.validators.max_foos_validator',
}

MANAGE_PY_PATH = os.environ.get("MANAGE_PY_PATH", './manage.py')

PLANS_CURRENCY = 'EUR'

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

LOGIN_REDIRECT_URL = '/foo/list/'

ENABLE_FAKE_PAYMENTS = True

if os.environ.get('SAMPLE_APP', False):
    INSTALLED_APPS.remove('plans')
    INSTALLED_APPS.append('example.sample_plans')

    PLANS_PLAN_MODEL = 'sample_plans.Plan'
    PLANS_BILLINGINFO_MODEL = 'sample_plans.BillingInfo'
    PLANS_USERPLAN_MODEL = 'sample_plans.UserPlan'
    PLANS_PRICING_MODEL = 'sample_plans.Pricing'
    PLANS_PLANPRICING_MODEL = 'sample_plans.PlanPricing'
    PLANS_QUOTA_MODEL = 'sample_plans.Quota'
    PLANS_PLANQUOTA_MODEL = 'sample_plans.PlanQuota'
    PLANS_ORDER_MODEL = 'sample_plans.Order'
    PLANS_INVOICE_MODEL = 'sample_plans.Invoice'
    PLANS_RECURRINGUSERPLAN_MODEL = 'sample_plans.RecurringUserPlan'

    # Celery auto detects tasks only from INSTALLED_APPS
    CELERY_IMPORTS = ('openwisp_notifications.tasks',)
