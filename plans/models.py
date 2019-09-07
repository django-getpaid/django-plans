from swapper import swappable_setting

from decimal import Decimal
from datetime import date, timedelta

from django.db import models, transaction
from django.template import Context
from django.template.base import Template
from django.utils import translation
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _, pgettext_lazy

from plans.base.models import (AbstractPlan, AbstractBillingInfo, AbstractUserPlan,
                               AbstractPricing, AbstractPlanPricing, AbstractQuota,
                               AbstractPlanQuota, AbstractOrder, AbstractInvoice,
                               AbstractRecurringUserPlan)
from plans.enumeration import Enumeration
from plans.importer import import_name
from plans.validators import plan_validation
from plans.taxation.eu import EUTaxationPolicy
from plans.contrib import send_template_email, get_user_language
from plans.signals import (order_completed, account_activated,
                           account_expired, account_change_plan,
                           account_deactivated)
from sequences import get_next_value

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
