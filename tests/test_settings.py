from decimal import Decimal


SECRET_KEY = 'fake-key'
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',

    'plans',
    'tests',
]

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        # Add 'postgresql_psycopg2', 'postgresql', 'mysql', 'sqlite3' or 'oracle'.
        'NAME': 'tests.sqlite',  # Or path to database file if using sqlite3.
        'USER': '',  # Not used with sqlite3.
        'PASSWORD': '',  # Not used with sqlite3.
        'HOST': '',  # Set to empty string for localhost. Not used with sqlite3.
        'PORT': '',  # Set to empty string for default. Not used with sqlite3.
    }
}

USE_TZ = True

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
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

ROOT_URLCONF = 'plans.urls'

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
    'MAX_FOO_COUNT': 'tests.validators.max_foos_validator',
}

PLANS_CURRENCY = 'EUR'

PLANS_USER_BUYER_RELATION = 'profile.team.buyer'
PLANS_BUYER_EMAIL_RELATION = 'team.email'
