Installation
============

Installing module code
------------------------

You can install app using package manager directly from github:

.. code-block:: bash

    $ pip install django-plans


For integration instruction please see section  :doc:`integration`.



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
    $ python manage.py syncdb
    [...]
    Would you like to create one now? (yes/no): no
    [...]


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
