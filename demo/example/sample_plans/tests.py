from plans.tests.tests import BillingInfoTestCase as BaseBillingInfoTestCase
from plans.tests.tests import \
    BillingInfoViewTestCase as BaseBillingInfoViewTestCase
from plans.tests.tests import \
    ConcurrentTestInvoice as BaseConcurrentTestInvoice
from plans.tests.tests import \
    CreateOrderViewTestCase as BaseCreateOrderViewTestCase
from plans.tests.tests import \
    EUTaxationPolicyTestCase as BaseEUTaxationPolicyTestCase
from plans.tests.tests import OrderTestCase as BaseOrderTestCase
from plans.tests.tests import \
    PlanChangePolicyTestCase as BasePlanChangePolicyTestCase
from plans.tests.tests import PlansTestCase as BasePlansTestCase
from plans.tests.tests import \
    RecurringPlansTestCase as BaseRecurringPlansTestCase
from plans.tests.tests import \
    StandardPlanChangePolicyTestCase as BaseStandardPlanChangePolicyTestCase
from plans.tests.tests import TasksTestCase as BaseTasksTestCase
from plans.tests.tests import TestInvoice as BaseTestInvoice
from plans.tests.tests import ValidatorsTestCase as BaseValidatorsTestCase


class PlanTestCase(BasePlansTestCase):
    pass


class TestInvoice(BaseTestInvoice):
    pass


class ConcurrentTestInvoice(BaseConcurrentTestInvoice):
    pass


class OrderTestCase(BaseOrderTestCase):
    pass


class PlanChangePolicyTestCase(BasePlanChangePolicyTestCase):
    pass


class StandardPlanChangePolicyTestCase(BaseStandardPlanChangePolicyTestCase):
    pass


class EUTaxationPolicyTestCase(BaseEUTaxationPolicyTestCase):
    pass


class BillingInfoTestCase(BaseBillingInfoTestCase):
    pass


class CreateOrderViewTestCase(BaseCreateOrderViewTestCase):
    pass


class ValidatorsTestCase(BaseValidatorsTestCase):
    pass


class BillingInfoViewTestCase(BaseBillingInfoViewTestCase):
    pass


class RecurringPlansTestCase(BaseRecurringPlansTestCase):
    pass


class TasksTestCase(BaseTasksTestCase):
    pass


del BaseBillingInfoTestCase
del BaseBillingInfoViewTestCase
del BaseConcurrentTestInvoice
del BaseCreateOrderViewTestCase
del BaseEUTaxationPolicyTestCase
del BaseOrderTestCase
del BasePlanChangePolicyTestCase
del BasePlansTestCase
del BaseRecurringPlansTestCase
del BaseStandardPlanChangePolicyTestCase
del BaseTasksTestCase
del BaseTestInvoice
del BaseValidatorsTestCase
