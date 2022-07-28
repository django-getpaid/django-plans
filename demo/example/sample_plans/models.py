from django.db import models

from plans.base.models import (AbstractBillingInfo, AbstractInvoice,
                               AbstractOrder, AbstractPlan,
                               AbstractPlanPricing, AbstractPlanQuota,
                               AbstractPricing, AbstractQuota,
                               AbstractRecurringUserPlan, AbstractUserPlan)


class DetailFieldMixin:
    # Tests additional field can be added to the models
    detail = models.CharField(max_length=50, null=True, blank=True)


class BillingInfo(DetailFieldMixin, AbstractBillingInfo):
    class Meta(AbstractBillingInfo.Meta):
        abstract = False


class Invoice(DetailFieldMixin, AbstractInvoice):
    class Meta(AbstractInvoice.Meta):
        abstract = False


class Order(DetailFieldMixin, AbstractOrder):
    class Meta(AbstractOrder.Meta):
        abstract = False


class Plan(AbstractPlan):
    # Test existing fields can be modified
    default = models.BooleanField(
        help_text=AbstractPlan._meta.get_field('default').help_text,
        default=AbstractPlan._meta.get_field('default').default,
        null=True,
        blank=True,
    )

    class Meta(AbstractPlan.Meta):
        abstract = False


class PlanQuota(DetailFieldMixin, AbstractPlanQuota):
    class Meta(AbstractPlanQuota.Meta):
        abstract = False


class PlanPricing(DetailFieldMixin, AbstractPlanPricing):
    class Meta(AbstractPlanPricing.Meta):
        abstract = False


class Pricing(DetailFieldMixin, AbstractPricing):
    class Meta(AbstractPricing.Meta):
        abstract = False


class Quota(DetailFieldMixin, AbstractQuota):
    class Meta(AbstractQuota.Meta):
        abstract = False


class RecurringUserPlan(DetailFieldMixin, AbstractRecurringUserPlan):
    class Meta(AbstractRecurringUserPlan.Meta):
        abstract = False


class UserPlan(DetailFieldMixin, AbstractUserPlan):
    class Meta(AbstractUserPlan.Meta):
        abstract = False


class TestApp(DetailFieldMixin, models.Model):
    class Meta:
        abstract = False
