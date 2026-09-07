# coding=utf-8
from decimal import Decimal

from django.conf import settings

from plans.importer import import_name


class PlanChangePolicy(object):
    def _calculate_day_cost(self, plan, period):
        """
        Finds most fitted plan pricing for a given period, and calculate day cost
        """
        if plan.is_free():
            # If plan is free then cost is always 0
            return 0

        # Pricings of the same length (a monthly subscription next to a 30-day
        # trial) are ordered renewable first, then cheaper, then older, so the
        # same plan is always priced by the same row.
        plan_pricings = list(
            plan.planpricing_set.order_by(
                "pricing__period", "-has_automatic_renewal", "price", "pk"
            ).select_related("pricing")
        )
        if not plan_pricings:
            raise ValueError("Plan %s has no pricings." % plan)

        fitting = [pp for pp in plan_pricings if pp.pricing.period <= period]
        if fitting:
            # The longest pricing that fits in the period.
            longest = fitting[-1].pricing.period
            selected_pricing = next(
                pp for pp in fitting if pp.pricing.period == longest
            )
        else:
            # Nothing fits: the shortest pricing there is.
            selected_pricing = plan_pricings[0]
        return (selected_pricing.price / selected_pricing.pricing.period).quantize(
            Decimal("1.00")
        )

    def _calculate_final_price(self, period, day_cost_diff):
        if day_cost_diff is None:
            return None
        else:
            return period * day_cost_diff

    def get_change_price(self, plan_old, plan_new, period):
        """
        Calculates total price of plan change. Returns None if no payment is required.
        """
        if period is None or period < 1:
            return None

        plan_old_day_cost = self._calculate_day_cost(plan_old, period)
        plan_new_day_cost = self._calculate_day_cost(plan_new, period)

        if plan_new_day_cost <= plan_old_day_cost:
            return self._calculate_final_price(period, None)
        else:
            return self._calculate_final_price(
                period, plan_new_day_cost - plan_old_day_cost
            )


class StandardPlanChangePolicy(PlanChangePolicy):
    """
    This plan switch policy follows the rules:
        * user can downgrade a plan for free if the plan is
          cheaper or have exact the same price (additional constant charge can be applied)
        * user need to pay extra amount depending of plans price difference (additional constant charge can be applied)

    Change percent rate while upgrading is defined in ``StandardPlanChangePolicy.UPGRADE_PERCENT_RATE``

    Additional constant charges are:
        * ``StandardPlanChangePolicy.UPGRADE_CHARGE``
        * ``StandardPlanChangePolicy.FREE_UPGRADE``
        * ``StandardPlanChangePolicy.DOWNGRADE_CHARGE``

    .. note:: Example

        User has PlanA which costs monthly (30 days) 20 €. His account will expire in 23 days. He wants to change
        to PlanB which costs monthly (30 days) 50€. Calculations::

            PlanA costs per day 20 €/ 30 days = 0.67 €
            PlanB costs per day 50 €/ 30 days = 1.67 €
            Difference per day between PlanA and PlanB is 1.00 €
            Upgrade percent rate is 10%
            Constant upgrade charge is 0 €
            Switch cost is:
                       23 *            1.00 € *                  10% +                     0 € = 25.30 €
                days_left * cost_diff_per_day * upgrade_percent_rate + constant_upgrade_charge
    """

    UPGRADE_PERCENT_RATE = Decimal("10.0")
    UPGRADE_CHARGE = Decimal("0.0")
    DOWNGRADE_CHARGE = None
    FREE_UPGRADE = Decimal("0.0")

    def _calculate_final_price(self, period, day_cost_diff):
        if day_cost_diff is None:
            return self.DOWNGRADE_CHARGE
        cost = (
            period * day_cost_diff * (self.UPGRADE_PERCENT_RATE / 100 + 1)
            + self.UPGRADE_CHARGE
        ).quantize(Decimal("1.00"))
        if cost is None or cost < self.FREE_UPGRADE:
            return None
        else:
            return cost


def get_policy():
    policy_class = getattr(
        settings,
        "PLANS_CHANGE_POLICY",
        "plans.plan_change.StandardPlanChangePolicy",
    )
    return import_name(policy_class)()


def get_change_price(userplan, plan):
    policy = get_policy()

    if userplan.expire is not None:
        period = userplan.days_left()
    else:
        # Use the default period of the new plan
        period = 30

    return policy.get_change_price(userplan.plan, plan, period)
