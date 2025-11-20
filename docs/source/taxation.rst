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

The EU taxation policy now includes automatic VAT rate updates via the European Commission's TEDB (Taxes in Europe Database) service. VAT rates are cached for 24 hours and automatically fall back to updated static rates if the service is unavailable.

**Recent VAT Rate Updates (2024-2025):**
- Estonia: 22% (increased from 20% in January 2024)
- Finland: 25.5% (increased from 24% in September 2024)
- Slovakia: 23% (increased from 20% in January 2025)
- Romania: 21% (increased from 19% in August 2025)

.. note::
    This taxation policy requires ``zeep`` and ``python-stdnum`` modules (connecting to `VIES <http://ec.europa.eu/taxation_customs/vies/>`_ and `TEDB <https://ec.europa.eu/taxation_customs/tedb/>`_). These are automatically installed with django-plans.

``RussianTaxationPolicy``
-------------------------

FIXME: under developement

.. autoclass:: plans.taxation.ru.RussianTaxationPolicy
    :members:
    :undoc-members:
