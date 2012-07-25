Invoicing
=========

There is a built in support for creating invoices. This functionality brings powerful features like:
  * invoices are linked to orders,
  * invoices can have different shipping info,
  * invoices can be marked as "requiring shipment"
  * invoices can be previewed as HTML or PDF


Billing data
------------

First of all you should provide a way to input a billing data by the customer. Billing data are stored as model ``BillingInfo``.


.. autoclass:: plans.models.BillingInfo


There are four class-based views to manage deleting and adding billing data:

.. autoclass:: plans.views.BillingInfoRedirectView


.. autoclass:: plans.views.BillingInfoCreateView


.. autoclass:: plans.views.BillingInfoUpdateView


.. autoclass:: plans.views.BillingInfoDeleteView

Described views are pointed by following urls name patterns:
   * ``billing_info``,
   * ``billing_info_create``,
   * ``billing_info_update``,
   * ``billing_info_delete``.

Described views require creating following templates:
   * ``billing_info``,
   * ``plans/billing_info_create.html``,
   * ``plans/billing_info_update.html``,
   * ``plans/billing_info_delete.html``.
Basically you need only to manage ``{{ form }}`` displaying and sending within these templates.

Invoice model class
-------------------

.. autoclass:: plans.models.Invoice
   :members:
