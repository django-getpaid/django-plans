Working with South migrations
=============================

Because this project is designed with i18n and l10n in mind it supports translating some of model fields (e.g. plans names and descriptions). This feature is implemented using django-modeltranslation. Unfortunately this approach generate models on the fly - i.e. depending on activated translations in django settings.py it generate appropriate list of translated fields for every text field marked an translatable.

This bring a problem that south migrations cannot be made for an app itself due to lack of possibility to frozen such dynamically generated model. However you can still benefit from south migrations using django plans using an apporach presented in this document. We will use a great feature of South module, which isaccesible via `SOUTH_MIGRATION_MODULES <http://south.readthedocs.org/en/latest/settings.html#south-migration-modules>`_ setting.

This option allows you to overwrite default South migrations search path and create your own project dependent migrations in scope of your own project files. To setup custom migrations for your project follow these simple steps.

Step 1. Add ``SOUTH_MIGRATION_MODULES`` setting
-----------------------------------------------

You should put your custom migrations somewhere. The good place seems to be path ``PROJECT_ROOT/migrations/plans`` directory.

.. note::

    Remember that ``PROJECT_ROOT/migrations/plans`` path should be a python module, i.e. it needs to be importable from python.

Then put the following into ``settings.py``::


    SOUTH_MIGRATION_MODULES = {
        'plans' : 'yourproject.migrations.plans',
    }



Step 2. Create initial migration
--------------------------------

From now on, everything works like standard South migrations, with the only difference that migrations are kept in scope of your project files - not plans module files.

::

    $ python migrate.py schemamigration --initial plans


Step 3. Migrate changes on deploy
---------------------------------

::

    $ python migrate.py migrate plans



Step 4. Upgrading to new a version of plans
-------------------------------------------

When there is a new version of django-plans, you can upgrade your module by simply using South to generate custom migration::

    $ python migrate schemamigration --auto plans

and then::

    $ python migrate.py migrate plans
