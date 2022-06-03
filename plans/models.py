from swapper import swappable_setting

from plans.base.models import (AbstractBillingInfo, AbstractInvoice,
                               AbstractOrder, AbstractPlan,
                               AbstractPlanPricing, AbstractPlanQuota,
                               AbstractPricing, AbstractQuota,
                               AbstractRecurringUserPlan, AbstractUserPlan)


class Plan(AbstractPlan):
    class Meta(AbstractPlan.Meta):
        abstract = False
        swappable = swappable_setting('plans', 'Plan')


class BillingInfo(AbstractBillingInfo):
    class Meta(AbstractBillingInfo.Meta):
        abstract = False
        swappable = swappable_setting('plans', 'BillingInfo')


class UserPlan(AbstractUserPlan):
    class Meta(AbstractUserPlan.Meta):
        abstract = False
        swappable = swappable_setting('plans', 'UserPlan')


class Pricing(AbstractPricing):
    class Meta(AbstractPricing.Meta):
        abstract = False
        swappable = swappable_setting('plans', 'Pricing')


class PlanPricing(AbstractPlanPricing):
    class Meta(AbstractPlanPricing.Meta):
        abstract = False
        swappable = swappable_setting('plans', 'PlanPricing')


class Quota(AbstractQuota):
    class Meta(AbstractQuota.Meta):
        abstract = False
        swappable = swappable_setting('plans', 'Quota')


class PlanQuota(AbstractPlanQuota):
    class Meta(AbstractPlanQuota.Meta):
        abstract = False
        swappable = swappable_setting('plans', 'PlanQuota')


class Order(AbstractOrder):
    class Meta(AbstractOrder.Meta):
        abstract = False
        swappable = swappable_setting('plans', 'Order')


class Invoice(AbstractInvoice):
    class Meta(AbstractInvoice.Meta):
        abstract = False
        swappable = swappable_setting('plans', 'Invoice')


class RecurringUserPlan(AbstractRecurringUserPlan):

    class Meta(AbstractRecurringUserPlan.Meta):
        abstract = False
        swappable = swappable_setting('plans', 'RecurringUserPlan')
