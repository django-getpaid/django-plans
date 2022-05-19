Configuration via `settings`
============================

``Swappable models``
--------------------

Given a django app named ``custom_plans``, it's possible to supply
alternative models which extend the base models of django-plans by
defining the following settings:

.. code-block:: python

    PLANS_PLAN_MODEL = 'custom_plans.Plan'
    PLANS_BILLINGINFO_MODEL = 'custom_plans.BillingInfo'
    PLANS_USERPLAN_MODEL = 'custom_plans.UserPlan'
    PLANS_PRICING_MODEL = 'custom_plans.Pricing'
    PLANS_PLANPRICING_MODEL = 'custom_plans.PlanPricing'
    PLANS_QUOTA_MODEL = 'custom_plans.Quota'
    PLANS_PLANQUOTA_MODEL = 'custom_plans.PlanQuota'
    PLANS_ORDER_MODEL = 'custom_plans.Order'
    PLANS_INVOICE_MODEL = 'custom_plans.Invoice'

``PLANS_CURRENCY``
------------------

**Required**

Three letter code for system currency. Should always be capitalized.

Example::

    PLANS_CURRENCY = 'EUR'


``DEFAULT_FROM_EMAIL``
----------------------

**Required**

This is the default mail ``FROM`` value for sending system notifications.

``PLANS_GET_COUNTRY_FROM_IP``
-----------------------------

**Optional**

Default: ``False``

If set to True, the country default in billing info will be get from users IP.
The ``geolite2`` library must be installed for this to work.


``PLANS_INVOICE_COUNTER_RESET``
-------------------------------

**Optional**

Default: ``monthly``

This settings switches invoice counting per days, month or year basis. It requires to
provide one of the value or a callable:

 * Invoice.NUMBERING.DAILY
 * Invoice.NUMBERING.MONTHLY
 * Invoice.NUMBERING.ANNUALY

Example::

    PLANS_INVOICE_COUNTER_RESET = Invoice.NUMBERING.MONTHLY

The callable takes the invoce and should return following values in tuple:

 * sequence identifier - any string, every it's value will hold separate sequence
 * initial number - minimal initail value for the sequence
   This is usefull for backward compatibility with sequences before the sequence identifier was introduced
   In case whithout prevous invoices in the system, just return `None`

Example (get separate counter for each currency)::

   def PLANS_INVOICE_COUNTER_RESET(invoice):
       from plans.models import Invoice
       from plans.base.models import get_initial_number
       older_invoices = Invoice.objects.filter(
           type=invoice.type,
           issued__year=invoice.issued.year,
           issued__month=invoice.issued.month,
           currency=invoice.currency,
       )
       sequence_name = f"{invoice.issued.year}_{invoice.issued.month}_{invoice.currency}"
       return sequence_name, get_initial_number(older_invoices)

.. warning::

    Remember to set ``PLANS_INVOICE_NUMBER_FORMAT`` manually to match preferred way of invoice numbering schema. For example if
    you choose reset counter on daily basis, you need to use in ``PLANS_INVOICE_NUMBER_FORMAT`` at least ``{{ invoice.issued|date:'d/m/Y' }}``
    to distinguish invoice's full numbers between days.


``PLANS_INVOICE_NUMBER_FORMAT``
-------------------------------

**Optional**

Default: ``"{{ invoice.number }}/{% ifequal invoice.type invoice.INVOICE_TYPES.PROFORMA %}PF{% else %}FV{% endifequal %}/{{ invoice.issued|date:'m/Y' }}"``

A django template syntax format for rendering invoice full number. Within this template you can use one variable
``invoice`` which is an instance of ``Invoice`` object.


Example::

    PLANS_INVOICE_NUMBER_FORMAT = "{{ invoice.number }}/{{ invoice.issued|date='m/FV/Y' }}"

This example for invoice issued on ``March 5th, 2010``, with sequential number ``13``, will produce the full number
``13/03/FV/2010`` or ``13/03/PF/2010`` based on invoice type.

.. warning::

   Full number of an invoice is saved with the Invoice object. Changing this value in settings will affect only newly created invoices.

``PLANS_INVOICE_LOGO_URL``
--------------------------

**Optional**

Default: ``None``

URL of logo image that should be placed in an invoice. It will be available in invoice template as ``{{ logo_url }}`` context variable.


Example::

    from urllib.parse import urljoin
    PLANS_INVOICE_LOGO_URL = urljoin(STATIC_URL, 'my_logo.png')





``PLANS_INVOICE_TEMPLATE``
--------------------------

**Optional**

Default: ``'plans/invoices/PL_EN.html'``


Template name for displaying invoice.

.. warning::

    Invoices are generated on the fly from database records. Therefore  changing this value will affect all
    previously created invoices.


Example::

    PLANS_INVOICE_TEMPLATE = 'plans/invoices/PL_EN.html'




``PLANS_INVOICE_ISSUER``
------------------------
**Required**

You need to define a dictionary that will store information needed to issue an invoice. Fill dict fields as in an example.

Example::

    PLANS_INVOICE_ISSUER = {
        "issuer_name": "Joe Doe Company",
        "issuer_street": "Django street, 34",
        "issuer_zipcode": "123-3444",
        "issuer_city": "Djangoko",
        "issuer_country": "Djangoland",
        "issuer_tax_number": "1222233334444555",
    }





``PLANS_ORDER_EXPIRATION``
--------------------------

**Optional**

Default: ``14``


A number of days that an Order is valid (e.g. to start a payment) counting from order creation date. This value is only used in ``is_ready_for_payment()`` method for django-getpaid integration. This value has no effect on processing already paid orders before ``PLANS_ORDER_EXPIRATION`` period, even if confirmation for this payment will came after ``PLANS_ORDER_EXPIRATION`` period.

Example::

    PLANS_ORDER_EXPIRATION = 14


.. _settings-EXPIRATION_REMIND:

``PLANS_EXPIRATION_REMIND``
---------------------------

**Optional**

Application is responsible for expiring user accounts.
Before account became expired it is able to send expiration warnings to the users by `expire_account` task (:doc:`plans_expiration`).
This setting should contain a list of numbers, that corresponds to days before expiration period. User will
receive expiration warning at each moment from that list.

Default: ``[]``

Example::

    PLANS_EXPIRATION_REMIND = [1, 3 , 7]


User will receive notification before 7 , 3 and 1 day to account expire.


``PLANS_CHANGE_POLICY``
-----------------------

**Optional**

Default: ``'plans.plan_change.StandardPlanChangePolicy'``

A full python to path that should be used as plan change policy.

``PLANS_DEFAULT_GRACE_PERIOD``
------------------------------

**Optional**

Default: ``30``


New account default plan expiration period counted in days.


Example::

    PLANS_DEFAULT_GRACE_PERIOD = 30



.. note::

    Default plan should be selected using site admin. Set default flag to one of available plans.



``PLANS_VALIDATORS``
--------------------

**Optional**

Default: ``{}``

A dict that stores mapping ``"Quota codename" : "validator object"``. Validators are used to check if user account
can be activated for the given plan. Account cannot exceed certain limits introduced by quota.

Given account will be activated only if calling all validators that are defined with his new plan does not raise any ValidationError. If account cannot be activated user will be noticed after logging with information that account needs activation.

Example::


    PLANS_VALIDATORS = {
        'CAN_DO_SOMETHING' :  'myproject.validators.can_do_something_validator',
        'MAX_STORAGE' :  'myproject.validators.max_storage_validator',
    }

The dict itself could be also lazy imported string::

    PLANS_VALIDATORS = 'myproject.validators.validator_dict'


Further reading: :doc:`quota_validators`

``SEND_PLANS_EMAILS``
---------------------

**Optional**

Default: ``True``

Boolean value for enabling (default) or disabling the sending of plan related emails.

``PLANS_SEND_EMAILS_DISABLED_INVOICE_TYPES``
--------------------------------------------

**Optional**

Default: ``[]``

Disable listed invoice types to be send via e-mails.

``PLANS_SEND_EMAILS_PLAN_CHANGED``
----------------------------------

**Optional**

Default: ``True``

Disable plans changed e-mail.

``PLANS_SEND_EMAILS_PLAN_EXTENDED``
-----------------------------------

**Optional**

Default: ``True``

Disable plan extended e-mail.


``PLANS_TAX``
-------------

**Required**

Decimal or integer value for default TAX (usually referred as VAT).

Example::

    from decimal import Decimal
    PLANS_TAX = Decimal('23.0')  # for 23% VAT

Default: ``None``

.. warning::

   The value ``None`` means "TAX not applicable, rather than value ``Decimal('0')`` which is 0% TAX.


.. _settings-TAXATION_POLICY:

``PLANS_TAXATION_POLICY``
-------------------------

**Required**

Class that realises taxation of an order.

Example::

    PLANS_TAXATION_POLICY='plans.taxation.eu.EUTaxationPolicy'


Further reading: :doc:`taxation`

``PLANS_DEFAULT_COUNTRY``
-------------------------

**Optional**

Two letter ISO country code. This variable is used to determine default country for user on his billing info.

Example::

    PLANS_TAX_COUNTRY = 'PL'

``PLANS_TAX_COUNTRY``
---------------------

**Optional**

Two letter ISO country code. This variable is used to determine origin issuers country. Taxation policy uses this value to determine tax amount for any order.

Example::

    PLANS_TAX_COUNTRY = 'PL'

``PLANS_APP_VERBOSE_NAME``
--------------------------

**Optional**

Default: ``plans``

The ``verbose_name`` of django-plans' ``AppConfig``.

.. note::

    ``settings.PLANS_TAX_COUNTRY`` is a separate value from ``settings.PLANS_INVOICE_ISSUER.issuer_country`` on purpose. ``PLANS_INVOICE_ISSUER`` is just what you want to have printed on an invoice.

``PLANS_AUTORENEW_BEFORE_DAYS`` and ``PLANS_AUTORENEW_BEFORE_HOURS``
--------------------------------------------------------------------

**Optional**

Default: ``0`` (for both)

Time of plan automatic renewal before the plan actually expires.
