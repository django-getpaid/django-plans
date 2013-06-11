Configuration via `settings`
============================


``CURRENCY``
------------

**Required**

Three letter code for system currency. Should always be capitalized.

Example::

    CURRENCY = 'EUR'


``DEFAULT_FROM_EMAIL``
----------------------

**Required**

This is the default mail ``FROM`` value for sending system notifications.

``INVOICE_COUNTER_RESET``
-------------------------

**Optional**

Default: ``monthly``

This settings switches invoice counting per days, month or year basis. It requires to
provide one of following string format:

 * ``daily``
 * ``monthly``
 * ``annually``

Example::

    INVOICE_COUNTER_RESET = 'yearly'

.. warning::

    Remember to set ``INVOICE_NUMBER_FORMAT`` manually to match preferred way of invoice numbering schema. For example if
    you choose reset counter on daily basis, you need to use in ``INVOICE_NUMBER_FORMAT`` at least ``{{ invoice.issued|date:'d/m/Y' }}``
    to distinguish invoice's full numbers between days.


``INVOICE_NUMBER_FORMAT``
-------------------------

**Optional**

Default: ``"{{ invoice.number }}/{% ifequal invoice.type invoice.INVOICE_TYPES.PROFORMA %}PF{% else %}FV{% endifequal %}/{{ invoice.issued|date:'m/Y' }}"``

A django template syntax format for rendering invoice full number. Within this template you can use one variable
``invoice`` which is an instance of ``Invoice`` object.


Example::

    INVOICE_NUMBER_FROMAT = "{{ invoice.number }}/{{ invoice.issued|date='m/FV/Y' }}"

This example for invoice issued on ``March 5th, 2010``, with sequential number ``13``, will produce the full number
``13/03/FV/2010`` or ``13/03/PF/2010`` based on invoice type.

.. warning::

   Full number of an invoice is saved with the Invoice object. Changing this value in settings will affect only newly created invoices.

``INVOICE_LOGO_URL``
--------------------

**Optional**

Default: ``None``

URL of logo image that should be placed in an invoice. It will be available in invoice template as ``{{ logo_url }}`` context variable.


Example::

    from urllib.parse import urljoin
    INVOICE_LOGO_URL = urljoin(STATIC_URL, 'my_logo.png')





``INVOICE_TEMPLATE``
--------------------

**Optional**

Default: ``'plans/invoices/PL_EN.html'``


Template name for displaying invoice.

.. warning::

    Invoices are generated on the fly from database records. Therefore  changing this value will affect all
    previously created invoices.


Example::

    INVOICE_TEMPLATE = 'plans/invoices/PL_EN.html'




``ISSUER_DATA``
---------------
**Required**

You need to define a dictionary that will store information needed to issue an invoice. Fill dict fields as in an example.

Example::

    ISSUER_DATA = {
        "issuer_name": "Joe Doe Company",
        "issuer_street": "Django street, 34",
        "issuer_zipcode": "123-3444",
        "issuer_city": "Djangoko",
        "issuer_country": "Djangoland",
        "issuer_tax_number": "1222233334444555",
    }





``ORDER_EXPIRATION``
--------------------

**Optional**

Default: ``14``


A number of days that an Order is valid (e.g. to start a payment) counting from order creation date. This value is only used in ``is_ready_for_payment()`` method for django-getpaid integration. This value has no effect on processing already paid orders before ``ORDER_EXPIRATION`` period, even if confirmation for this payment will came after ``ORDER_EXPIRATION`` period.

Example::

    ORDER_EXPIRATION = 14


``PLAN_EXPIRATION_REMIND``
--------------------------

**Optional**

Application is responsible for expiring user accounts. Before account became expired it is able to send expiration warnings to the users.
This setting should contain a list of numbers, that corresponds to days before expiration period. User will
receive expiration warning at each moment from that list.

Default: ``[]``

Example::

    PLAN_EXPIRATION_REMIND = [1, 3 , 7]


User will receive notification before 7 , 3 and 1 day to account expire.


``PLAN_CHANGE_POLICY``
----------------------

**Optional**

Default: ``'plans.plan_change.StandardPlanChangePolicy'``

A full python to path that should be used as plan change policy.

``PLAN_DEFAULT_GRACE_PERIOD``
-----------------------------

**Optional**

Default: ``30``


New account default plan expiration period counted in days.


Example::

    PLAN_DEFAULT_GRACE_PERIOD = 30



.. note::

    Default plan should be selected using site admin. Set default flag to one of available plans.



``PLAN_ACTIVATION_VALIDATORS``
------------------------------

**Optional**

Default: ``{}``

A dict that stores mapping ``"Quota codename" : "validator object"``. Validators are used to check if user account
can be activated for the given plan. Account cannot exceed certain limits introduced by quota.

Given account will be activated only if calling all validators that are defined with his new plan does not raise any ValidationError. If account cannot be activated user will be noticed after logging with information that account needs activation.

Example::


    PLAN_ACTIVATION_VALIDATORS = {
        'CAN_DO_SOMETHING' :  'myproject.validators.can_do_something_validator',
        'MAX_STORAGE' :  'myproject.validators.max_storage_validator',
    }


Further reading: :doc:`quota_validators`

``TAX``
-------

**Required**

Decimal or integer value for default TAX.

Example::

    from decimal import Decimal
    TAX = Decimal(23.0) #for 23% VAT

Default: ``None``

.. warning::

   The value ``None`` means "TAX not applicable, rather than value ``Decimal(0)`` which means 0% TAX.


.. _settings-TAXATION_POLICY:

``TAXATION_POLICY``
-------------------

**Required**

Class that realises taxation of an order.

Example::

    TAXATION_POLICY='plans.taxation.EUTaxationPolicy'


Further reading: :doc:`taxation`

``TAX_COUNTRY``
---------------

**Optional**

Two letter ISO country code. This variable is used to determine origin issuers country. Taxation policy uses this value to determine tax amount for any order.

Example::

    TAX_COUNTRY = 'PL'



.. note::

    ``settings.TAX_COUNTRY`` is a separate value from ``settings.ISSUER_DATA.issuer_country`` on purpose. ``ISSUER_DATA`` is just what you want to have printed on an invoice.