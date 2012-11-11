Installation
============

Setup for django project
------------------------

You can install app using package manager directly from github:

.. code-block:: bash

    $ pip install -e git://github.com/cypreess/django-plans.git#egg=django-plans

Now you need to configure your project. Add this app to your ``INSTALED_APPS`` setting::

    INSTALLED_APPS += ('plans', )

Define all **required** settings options described in :doc:`settings`, consider also adding :doc:`middleware` and Context Processor described in :doc:`templating`.

Don't forget to run ``manage.py syncdb`` in your project. South migrations are not supported at this moment as it is difficult to handle dynamically generated models in South.




Running example project
-----------------------

Clone git repository to your current directory:

.. code-block:: bash

    $ git clone git://github.com/cypreess/django-plans.git


Optionally create virtual env and get required packages to run example project:

.. code-block:: bash

    $ cd django-plans/example
    $ pip install -r pip_example.req


Initialize example project database:

.. code-block:: bash

    $ cd ..
    $ python manage.py syncdb

Load an initial data (used also for testing):

.. code-block:: bash

    $ python manage.py loaddata test_django-plans_auth test_django-plans_plans


Start dev webserver:

.. code-block:: bash

    $ python manage.py runserver
