django-plans-i18n
=================

django-plans internationalization using django-modeltranslation.

Installation
============

Assuming you have correctly installed django-plans in your app you only need to add following apps to ``INSTALLED_APPS``::

    INSTALLED_APPS += ('modeltranslation', 'plans_i18n')

and you should also define your languages in django ``LANGUAGES`` variable, eg.::

    LANGUAGES = (
        ('pl', 'Polski'),
        ('en', 'English'),
        )

Please note that adding those to ``INSTALLED_APPS`` **changes** django models. Concretely for every registered ``field`` that should be translated  it adds  number of fields using format ``field_<lang_code>``, e.g. for given model::

    class MyModel(models.Model):
        name = models.CharField(max_length=10)

Following fields will be present in MyModel: ``name`` , ``name_en``, ``name_pl``.

To apply those changes please migrate your database. E.g. using South you need to run following commands::

    $ python manage.py schemamigration --auto plans
    $ python migrate plans

Please notice that you will use a custom migration for your project. It usually requires to configure ``SOUTH_MIGRATION_MODULES``.

This app will also make all required adjustments in django admin.

For more info on how translation works in details please refer to `django-modeltranslation docs<https://django-modeltranslation.readthedocs.org/en/latest/>`_.






