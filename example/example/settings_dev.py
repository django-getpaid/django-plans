from settings import *

MIDDLEWARE_CLASSES += (
    'debug_toolbar.middleware.DebugToolbarMiddleware',
)


INTERNAL_IPS = ('127.0.0.1',)

DEBUG_TOOLBAR_CONFIG ={
    'INTERCEPT_REDIRECTS' : False,
}




INSTALLED_APPS += (
    'debug_toolbar',
    'django_extensions',
)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'mail_admins': {
            'level': 'ERROR',
            'class': 'django.utils.log.AdminEmailHandler'
        },
        'file_accounts' : {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': os.path.join(SITE_ROOT, 'accounts.log'),
        }
    },
    'loggers': {
        'django.request': {
            'handlers': ['mail_admins'],
            'level': 'ERROR',
            'propagate': True,
        },
        'accounts': {
            'handlers': ['file_accounts'],
            'level': 'INFO',
            'propagate': True,
        },
    }
}