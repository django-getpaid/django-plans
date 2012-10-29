Configuration via `settings`
============================


``CURRENCY``
------------

**Required**

Three letter code for system currency. Should be always capitalized.

Example::

    CURRENCY = 'EUR'


``DEFAULT_FROM_EMAIL``
----------------------

**Required**

This is the default mail ``FROM`` value for sending system notifications.

``INVOICE_COUNTER_RESET``
-------------------------

**Optional**

This settings switches invoice counting per days, month or year basis. It requires to
provide one of following string format:

 * ``daily``
 * ``monthly``
 * ``annually``


Default: ``monthly``

Example::

    INVOICE_COUNTER_RESET = 'yearly'

.. warning::

    Remember to set ``INVOICE_NUMBER_FORMAT`` manually to match preferred way of invoice numbering schema. For example if
    you choose reset counter on daily basis, you need to use in ``INVOICE_NUMBER_FORMAT`` at least ``{{ invoice.issued|date:'d/m/Y' }}``
    to distinguish invoice's full numbers between days.


``INVOICE_NUMBER_FORMAT``
-------------------------

**Optional**

A django template syntax format for rendering invoice full number. Within this template you can use one variable
``invoice`` which is an instance of ``Invoice`` object.

Default: ``"{{ invoice.number }}/{% ifequal invoice.type invoice.INVOICE_TYPES.PROFORMA %}PF{% else %}FV{% endifequal %}/{{ invoice.issued|date:'m/Y' }}"``

Example::

    INVOICE_NUMBER_FROMAT = "{ invoice.number }}/{{ invoice.issued|date='m/FV/Y' }}"

This example for invoice issued on ``March 5th, 2010``, with sequential number ``13``, will produce the full number
``13/03/FV/2010`` or ``13/03/PF/2010`` based on invoice type.

.. warning::

   Full number of an invoice is saved with the Invoice object. Changing this value in settings will affect only newly created invoices.

``INVOICE_LOGO_URL``
--------------------

**Optional**

URL of logo image that should be placed in an invoice. It will be available in invoice template as ``{{ logo_url }}`` context variable.

Default: ``None``

Example::

    INVOICE_LOGO_URL = STATIC_URL + 'my_logo.png'




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



``TAX``
-------

**Required**

Decimal value for default TAX.

Example::

    from decimal import Decimal
    TAX = Decimal(23.0) #for 23% VAT

Default: ``None``

.. warning::

   The value ``None`` means "TAX not applicable, rather than value ``Decimal(0)`` which means 0% TAX.


``VAT_COUNTRY``
---------------

**Optional**

Two letter ISO country code. This variable is used to determine all purchases made from outside countries.
If VAT ID number is successfully checked against VIES system, system will automatically set ``TAX = None`` (not applicable), but only for this one purchase.

VIES system is checked every time a customer makes new order (or once per sessions).

Example::

    VAT_COUNTRY = 'PL'


.. warning::

    This option is suitable only to use for European countries.



``PLAN_DEFAULT_GRACE_PERIOD``

**Optional**

How many days activate a default plan for a new account.

Default: 30

Example::

    PLAN_DEFAULT_GRACE_PERIOD = 30



.. note::

    Default plan should be selected using site admin. Set default flag to one of available plans.

``INVOICE_PROJECT_NAME``

**Required**

Name of service that will be used in the purchase item name of an invoice.

Default: ``u''``


Example::

    INVOICE_PROJECT_NAME = u'MyService.com'
