Taxation Policies
=================

Creating new order is a process that apart from counting item values depends also on specific rules how to apply a tax to the order. Django-plans is designed with internationalization in mind, therefore the way that the module calculates additional tax for an order is highly customizable and depends in general on locale.

For each country, or more generally for each specific use, there need to be created specific taxation policy which defines what rate of tax is suitable for an order depending on issuer country and customer billing data.

Taxation policy can be defined as a simple class that should inherit from ``plans.taxation.TaxationPolicy`` and provide ``get_default_tax(vat_id, country_code)`` method. Having arguments like customer

.. autoclass:: plans.taxation.TaxationPolicy
    :members:
    :undoc-members:

Django-plans application is shipped with some default taxation policies. You can choose them via :ref:`settings-TAXATION_POLICY` variable.

``EUTaxationPolicy``
--------------------

.. autoclass:: plans.taxation.eu.EUTaxationPolicy




.. note::
    This taxation policy requires ``suds`` (we use suds-jurko) and ``vatnumber`` python modules (connecting to `VIES <http://ec.europa.eu/taxation_customs/vies/>`_). If you want them automatically installed please remember to insert extra depedencies for pip::

        $ pip install django-plans[eu]

``RussianTaxationPolicy``
-------------------------

FIXME: under developement

.. autoclass:: plans.taxation.ru.RussianTaxationPolicy
    :members:
    :undoc-members:

