Welcome to django-plans
=======================

.. image:: https://travis-ci.org/cypreess/django-plans.svg?branch=master   
   :target: https://travis-ci.org/cypreess/django-plans
   
Django-plans is a pluggable app for managing pricing plans with quotas and accounts expiration. 
Features currently supported:

* multiple plans,
* support for user custom plans,
* flexible model for parametrizing plans (quota),
* customizable billing periods (plan pricing),
* order total calculation using customizable taxation policy (e.g. in EU calculating VAT based on seller/buyer countries and VIES)
* invoicing,
* account expiratons + e-mail remainders.

Documentation: https://django-plans.readthedocs.org/

Master branch: Support for django 2.0, support for py3.6

.. image:: docs/source/_static/images/django-plans-1.png

.. image:: docs/source/_static/images/django-plans-2.png

.. image:: docs/source/_static/images/django-plans-3.png
