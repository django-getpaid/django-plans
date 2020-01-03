Plans and pricing definition
============================

All definition of an offer (like plans, options, pricing, etc...) is made by
django admin panel. That means that there no need to make any hardcoded definitions of plans,
they are stored in the database.

Engine allows for the following customisation:

* Many plans can be defined, plan can be considered as a named group of account features for a specific price in specific period.
* Many pricing periods can be defined (e.g. monthly, annually, quarterly or any other), pricing is basically named amount of days.
* Many types of account feature (called quotas) can be defined (eg. maximum number of some items, account transfer limit, does the account is allowed to customize something).
* Plan without any pricing is considerd to be free plan. Without pricing it has no expiration.
* After defining quotas, each plan can define its own set of quotas with given values.
* I18n is supported in every aspect (in database text name fields also)


Plan
----

Plan stores information about single plan that is offered by a service. It is defined by the following properties:

``name``
````````

**type**: text

Plan name that is visible in headers, invoice, etc. This should be a short name like: "Basic", "Premium", "Pro".

.. note::

    This field supports i18n. In admin view you will be able to input this name in all available languages.

``description``
```````````````

**type**: text

Stores a short description for the plan that will be used in various places mostly for marketing purposes, eg. "For small groups", "Best value for medium companies", etc.

.. note::

    This field supports i18n. In admin view you will be able to input this name in all available languages.

``available``
`````````````

**type**: boolean

Only plans that are marked as ``available`` will be enabled to buy for the customers.

.. warning::

    You should never delete once created ``Plan`` unless you are sure that nobody is using it. If you want
    to stop offering some plan to customers, just mark it ``unavailable`` and create other plan (even with
    the same name; plan name is not unique in the system). Users will be asked to switch to the other plan
    when they will
    try to extend their accounts bound to Plan which is not available.

``customized``
``````````````

**type**: ``User``

Setting ``customized`` value to a specific users creates a special ``Plan`` that will be available only
for that one user. This allows to setup a tailored ``Plans`` that are not available for public.

.. note::

    Plan that is customized for a user need to be also ``available`` if user need to be able to buy this
    plan.

.. note::

    It is not possible to share one customized plan for two users. Even if plans are the same, there must be
    two identical custom plans for both users.


List of ``pricing`` periods
```````````````````````````

**type**: Many-to-many with ``Pricing`` by ``PlanPricing``

Many pricing periods can be defined for a given plan. For each entry there is a need of defining price. The currency
of price is defined by ``settings.PLANS_CURRENCY``.

.. warning::

    It is not possible to define multiple price currencies in the system. You can define only one type of currency
    and it will describe a currency of all amounts in the system.

.. note::

    Not all plans need necessarily to define all available pricing periods. Therefore a single plan need to define
    at least single pricing period, because it will be not possible to buy one without it.

List of ``quotas``
``````````````````

**type**: Many-to-many with ``Quota`` by ``PlanQuota``

Account that uses a given ``Plan`` can have various restrictions. Those restrictions are realised by ``Quota`` parameter. Each plan can have defined multiple set of ``Quota`` parameters with theirs corresponding values.

Please refer to ``Quota`` documentation for description of parameters types.

.. warning::

    Unless you know what you are doing all available plans should have defined the same set of quotas.


.. note::

    Omitting value for integer type quota is interpreted as "no limit".

Quota
-----

Quota represents a single named parameter that can be given to restrict functionality in the system. Parameters can have two types:

* integer type - ``is_boolean`` is off, then the value for a ``Quota`` will be interpreted as numerical (integer) restriction (e.g. "number of photos").
* boolean type - ``is_boolean`` is on, the value will be interpreted as boolean flag (e.g. "user can add photos").

.. warning::

    Making actual
    restrictions based on that values is a part of development process and is not covered here. In admin module
    you can only define any named quotas, but of course it will not magically affect anything unless any part of code
    implement some restrictions based on that.

Quota is made of following fields:

``codename``
````````````

**type**: string

This is a name for internal use by developers. They can use this name to identity quotas in the system and fetch their values.

``name``
````````

**type**: string

Human readable name of restriction (e.g. "Total number of photos")

.. note::

    This field supports i18n. In admin view you will be able to input this name in all available languages.

``unit``
````````

**type**: string

For displaying purposes you can define a unit that will be displayed after value (e.g. "MB").

.. note::

    This field supports i18n. In admin view you will be able to input this name in all available languages.

``description``
```````````````

**type**: string


Short description of the restriction (e.g. "This is a limit of total photos that you can have in your account")

.. note::

    This field supports i18n. In admin view you will be able to input this name in all available languages.


``is_boolean``
``````````````

**type**: boolean

This field flags this restriction as boolean type field. Value of this quota will be evaluated to ``True`` or ``False``
to determine provided option.


Pricing
-------

Pricing defines a single period of time that can be billed and account can be extended for this period. Because
periods can be named differently in many languages you can provide following properties for this objects:

``name``
````````

**type**: string

Pricing period name (e.g. "Monthly", "Month", "Full 30 days", "Annually", etc.)

.. note::

    This field supports i18n. In admin view you will be able to input this name in all available languages.

``period``
``````````

**type**: integer

Number that is representing a period in days (e.g. for month - ``30``, for annual - ``365``, etc.)