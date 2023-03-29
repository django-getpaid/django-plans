Installation
============

Installing module code
------------------------

You can install app using package manager directly from github:

.. code-block:: bash

    $ pip install django-plans

Add following applications to `INSTALLED_APPS`::

    INSTALLED_APPS += (
        'plans',
        'sequences.apps.SequencesConfig',
    )

For integration instruction please see section  :doc:`integration`.

If you want to determine billing info default country by IP address, install `geolite2`:

.. code-block:: bash

    $ pip install maxminddb-geolite2


Invoice sequences
-----------------

The `django-plans` application use `django-sequences` to generate sequence of invoice numbers without gaps and duplicities.
Be aware, that if the database isolation level is set to `ISOLATION_LEVEL_REPEATABLE_READ` or `ISOLATION_LEVEL_SERIALIZABLE`,
the concurrent creation of two invoices could throw `OperationalError: could not serialize access due to concurrent update`.
If you use such non-default isolation levels, you can either ignore this (if you think, that creation of two invoices at the
same time is highly inprobable in your app), repeat the operation or set different isolation level only for invoice creation transaction with::

    from django.db import connection

    with transaction.atomic():
        cursor = connection.cursor()
        cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')


Running example project
-----------------------

Clone git repository to your current directory:

.. code-block:: bash

    $ git clone git://github.com/cypreess/django-plans.git


Optionally create virtual environment and get required packages to run example project:

.. code-block:: bash

    $ cd django-plans/demo/
    $ pip install -r requirements.txt


Initialize example project database:

.. code-block:: bash

    $ cd ..
    $ python manage.py migrate


Initial example data will be loaded automatically.


Create `UserPlan` objects for all `User` objects:
This is done automatically during migrations, but any UserPlan is missing for whatever reason,
you can create it by management command.

.. code-block:: bash

    $ cd ..
    $ python manage.py create_userplans


Start development web server:

.. code-block:: bash

    $ python manage.py runserver

Visit http://localhost:8000/
