Integration
===========

TODO: write complete description

This section describes step by step how to integrate your application with django-plans.


Enable application in django
----------------------------

Add this app to your ``INSTALED_APPS`` in django settings.py::

    INSTALLED_APPS += ('plans', )

You should also define all other settings marked as **required** described in detail in section :doc:`settings`.

Don't forget to run::

    $ python manage.py syncdb


If you are going to use South migrations please read section :doc:`south`.


Enable context processor
-------------------------
Section :doc:`templating` describes a very helpful contet processor that you should definitelly enable in your project in this way::

        from django.conf import global_settings

        TEMPLATE_CONTEXT_PROCESSORS = global_settings.TEMPLATE_CONTEXT_PROCESSORS + (
            'plans.context_processors.expiration'
            )

Send signal when user account is fully activated
------------------------------------------------

You need to explicitly tell django-plans that user has fully activated account. django-plans provides a special signal that it listen to.

``plans.signals.activate_user_plan(user)``

You should send this signal providing ``user`` argument as an object of ``auth.User``. django-plans will use this information to initialize plan for this user, i.e. set expire date and make the plan active for this account.

.. note::

    If you use django-registration app for managing user registration process, you are done. django-plans automagically integrates with this app (if it is available) and will activate user plan when django-registration
    send it's signal of account activation.

