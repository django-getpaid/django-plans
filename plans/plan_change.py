# coding=utf-8
from decimal import Decimal

class PlanChangePolicy(object):

    def _calculate_day_cost(self, plan, period):
        """
        Finds most fitted plan pricing for a given period, and calculate day cost
        """

        plan_pricings = plan.planpricing_set.order_by('-pricing__period').select_related('pricing')
        selected_pricing = None
        for plan_pricing in plan_pricings:
            selected_pricing = plan_pricing
            if plan_pricing.pricing.period <= period:
                break

        if selected_pricing:
            return (selected_pricing.price / selected_pricing.pricing.period).quantize(Decimal('1.00'))

        raise ValueError('Plan %s has no pricings.' % plan)

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
            return self._calculate_final_price(period, plan_new_day_cost - plan_old_day_cost)



class StandardPlanChangePolicy(PlanChangePolicy):
    """
    This plan switch policy follows the rules:
        * user can downgrade a plan for free if the plan is cheaper or have exact the same price (additional constant charge can be applied)
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

    UPGRADE_PERCENT_RATE = Decimal('10.0')
    UPGRADE_CHARGE = Decimal('0.0')
    DOWNGRADE_CHARGE = None
    FREE_UPGRADE = Decimal('0.0')

    def _calculate_final_price(self, period, day_cost_diff):
        if day_cost_diff is None:
            return self.DOWNGRADE_CHARGE
        cost = (period * day_cost_diff * (self.UPGRADE_PERCENT_RATE/100 + 1) + self.UPGRADE_CHARGE).quantize(Decimal('1.00'))
        if cost is None or cost < self.FREE_UPGRADE:
            return None
        else:
            return cost
