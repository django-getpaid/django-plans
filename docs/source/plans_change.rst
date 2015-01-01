Plan change policies
====================

Changing (upgrading or downgrading) plan is another thing that can be highly customizable. You can choose which
ChangePlanPolicy should be used via ``PLANS_CHANGE_POLICY`` settings variable.


Plan change policy is a class that derives from ``plans.plan_change.PlanChangePolicy`` which should implement ``get_change_price(plan_old, plan_new, period)``. This method returns should return total price of changing current plan to new one, assuming that a given active period left on the account.

.. autoclass:: plans.plan_change.PlanChangePolicy
    :members:
    :undoc-members:

There are some default change plan policies already implemented.

``StandardPlanChangePolicy``
----------------------------

.. autoclass:: plans.plan_change.StandardPlanChangePolicy


.. note::

    Values of ``UPGRADE_CHARGE``, ``DOWNGRADE_CHARGE``, ``FREE_UPGRADE`` and ``UPGRADE_PERCENT_RATE`` can be customized by creating a custom change plan class that derives from ``StandardPlanChangePolicy``.