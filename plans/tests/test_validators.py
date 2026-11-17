from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.test import TestCase, override_settings
from example.foo.models import Foo
from example.foo.validators import MaxFoosValidator, max_foos_validator
from model_bakery import baker

from plans.validators import ModelAttributeValidator, QuotaValidator, plan_validation

User = get_user_model()


class OptionalMaxFoosValidator(MaxFoosValidator):
    required_to_activate = False


optional_max_foos_validator = OptionalMaxFoosValidator()


class LongNameValidator(ModelAttributeValidator):
    code = "MAX_FOO_NAME_LENGTH"
    model = Foo
    attribute = "name_length"

    def get_queryset(self, user):
        foos = list(Foo.objects.filter(user=user))
        for foo in foos:
            foo.name_length = len(foo.name)
        return foos


class QuotaValidatorTestCase(TestCase):
    def setUp(self):
        self.user = baker.make(User)
        plan = baker.make("Plan")
        self.foo_count_quota = baker.make("Quota", codename="MAX_FOO_COUNT")
        baker.make("PlanQuota", plan=plan, quota=self.foo_count_quota, value=1)
        name_quota = baker.make("Quota", codename="MAX_FOO_NAME_LENGTH")
        baker.make("PlanQuota", plan=plan, quota=name_quota, value=10)
        baker.make("UserPlan", user=self.user, plan=plan, expire=None)


class ModelCountValidatorTests(QuotaValidatorTestCase):
    def test_limit_is_read_from_the_users_plan(self):
        baker.make(Foo, user=self.user)
        self.assertIsNone(max_foos_validator(self.user))

        baker.make(Foo, user=self.user)
        with self.assertRaisesMessage(
            ValidationError, "Limit of foos exceeded. The limit is 1 items."
        ):
            max_foos_validator(self.user)

    def test_other_users_objects_do_not_count(self):
        baker.make(Foo, user=baker.make(User), _quantity=3)
        baker.make(Foo, user=self.user)

        self.assertIsNone(max_foos_validator(self.user))

    def test_validator_without_a_quota_code_is_a_configuration_error(self):
        class NoCodeValidator(QuotaValidator):
            pass

        with self.assertRaisesMessage(
            ImproperlyConfigured, "Quota code name is not provided for validator"
        ):
            NoCodeValidator().get_quota_value(self.user, {})


class ModelAttributeValidatorTests(QuotaValidatorTestCase):
    def test_objects_within_the_limit_pass(self):
        baker.make(Foo, user=self.user, name="short")
        baker.make(Foo, user=self.user, name="ten chars!")

        self.assertIsNone(LongNameValidator()(self.user))


class PlanValidationTests(QuotaValidatorTestCase):
    def test_required_validator_blocks_activation(self):
        baker.make(Foo, user=self.user, _quantity=2)

        errors = plan_validation(self.user)

        self.assertEqual(
            errors,
            {
                "required_to_activate": [
                    "Limit of foos exceeded. The limit is 1 items."
                ],
                "other": [],
            },
        )

    @override_settings(
        PLANS_VALIDATORS={
            "MAX_FOO_COUNT": "plans.tests.test_validators.optional_max_foos_validator"
        }
    )
    def test_optional_validator_only_reports(self):
        baker.make(Foo, user=self.user, _quantity=2)

        errors = plan_validation(self.user)

        self.assertEqual(
            errors,
            {
                "required_to_activate": [],
                "other": ["Limit of foos exceeded. The limit is 1 items."],
            },
        )

    def test_limits_of_another_plan_can_be_checked_before_ordering_it(self):
        bigger_plan = baker.make("Plan")
        baker.make("PlanQuota", plan=bigger_plan, quota=self.foo_count_quota, value=5)
        baker.make(Foo, user=self.user, _quantity=2)

        self.assertEqual(
            plan_validation(self.user, plan=bigger_plan),
            {"required_to_activate": [], "other": []},
        )
