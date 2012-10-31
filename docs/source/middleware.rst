Middleware
==========

django-plans comes with some handy middleware and context processor.

``plans.middleware.UserPlanMiddleware``
---------------------------------------

This middleware adds to request context a UserPlan object that is associated with current user. It requires authentication middleware to be installed before it.

Example::

    MIDDLEWARE_CLASSES = (
        'django.contrib.sessions.middleware.SessionMiddleware',
        'django.middleware.locale.LocaleMiddleware',
        'django.middleware.common.CommonMiddleware',
        'django.middleware.csrf.CsrfViewMiddleware',
        'django.contrib.auth.middleware.AuthenticationMiddleware',

        'plans.middleware.UserPlanMiddleware',

        'django.contrib.messages.middleware.MessageMiddleware',
        'django.middleware.clickjacking.XFrameOptionsMiddleware',

    )


.. warning::

    Be sure that all logged users have a User Plan.


