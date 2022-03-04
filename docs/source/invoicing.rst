Invoicing
=========

There is a built in support for creating invoices. This functionality brings powerful features like:
  * invoices are linked to orders,
  * invoices can have different shipping info,
  * invoices can be marked as "requiring shipment"
  * invoices can be previewed as HTML or PDF

Changing values of VAT tax and PLANS_INVOICE_ISSUER in a living system
----------------------------------------------------------------------

Your system can be running for a while. You can have a multiple orders and you could have issued a multiple invoices already.
There can be a situation that you need to change after a while a tax
or your company. This can be easily done by changing those data in django settings. This will
**not** affect any already created payment, order or invoice. System is designed in such way, that those information
are duplicated and stored within proper object in the moment of those object creation.

After changing those settings every new order, payment, invoice will use those new values.

.. warning::

    Remember that orders can be payed in some time window (e.g. 14 days). This mean that even if you change VAT tax rate,
    all your already created orders but not yet paid will have old tax. If this is what you don't want you
    need to cancel those orders manually and remember to contact your client that theirs orders were cancelled!

    This  however is not a case with ``PLANS_INVOICE_ISSUER`` change, because those data are taken in the same moment
    of issuing invoice. Even an old order will use new ``PLANS_INVOICE_ISSUER`` when invoicing a new payment.

Billing data
------------

First of all you should provide a way to input a billing data by the customer. Billing data are stored as model ``BillingInfo``.


.. autoclass:: plans.models.BillingInfo


There are four class-based views to manage deleting and adding billing data:

.. autoclass:: plans.views.BillingInfoRedirectView


.. autoclass:: plans.views.BillingInfoCreateOrUpdateView


.. autoclass:: plans.views.BillingInfoDeleteView

Described views are pointed by following urls name patterns:
   * ``billing_info``,
   * ``billing_info_create``,
   * ``billing_info_update``,
   * ``billing_info_delete``.

Described views require creating following templates:
   * ``billing_info``,
   * ``plans/billing_info_create_or_update.html``,
   * ``plans/billing_info_delete.html``.


Basically you need only to manage ``{{ form }}`` displaying and sending within these templates.

Invoice model class
-------------------

.. autoclass:: plans.models.Invoice
   :members:
