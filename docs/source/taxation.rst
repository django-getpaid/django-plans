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

Tax-inclusive orders
--------------------

An ``Order`` stores a net ``amount`` and a ``tax`` rate; ``Order.total()``
multiplies them and rounds to cents, and the invoice copies that split. This
treats the net price as the primary fact, which it is when the order is
created from a ``PlanPricing``.

Some payments are the other way round: the payment provider charges a fixed
tax-inclusive amount (a PayPal subscription, a merchant-of-record checkout,
a price list quoted with tax included) and the net has to be derived from
it. Multiplying a net cent value by a rate and rounding leaves gaps - at
21 % only 100 of every 121 gross cent values can be produced - so a charged
total such as 14.89 has no net amount that rounds to it (12.30 gives 14.88,
12.31 gives 14.90). The gap shows up as soon as a fixed-amount subscription
outlives a change of the customer's tax rate.

For these orders set ``gross_amount`` to the charged total and derive the
net with ``Order.net_from_gross()``, which applies the coefficient method
``tax = gross * rate / (100 + rate)`` (rounded half up) and returns
``gross - tax``::

    gross = Decimal("14.89")
    tax = Decimal("21")
    order = Order(
        amount=Order.net_from_gross(gross, tax),  # 12.31
        tax=tax,
        gross_amount=gross,
        ...
    )
    order.total()      # Decimal("14.89")
    order.tax_total()  # Decimal("2.58")

With ``gross_amount`` set, ``total()`` returns it and ``tax_total()`` is the
difference to the net amount, so ``amount + tax_total() == total()`` holds
on the cent grid and the invoice created from the order carries the amount
that was actually charged. Orders without ``gross_amount`` (the default, and
every order that predates the field) keep the net-based total.

``gross_amount`` is validated on ``clean()`` and ``save()``: it may differ
from ``amount * (1 + tax / 100)`` only by the rounding of the tax amount,
i.e. by less than one cent. A larger difference means the two fields
describe different prices and is rejected, so an invoice can never be
issued for a total that does not follow from its own net and rate.

.. note::
    The coefficient (top-down) computation of VAT is permitted by the EU VAT
    Directive next to the net-based one. Whether the tax authority of your
    issuing country accepts invoices split that way is for your accountant
    to confirm.
