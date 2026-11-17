from datetime import datetime, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.formats import date_format
from django.utils.timezone import localdate, localtime, make_aware, now
from model_bakery import baker

from plans.base.models import (
    AbstractBillingInfo,
    AbstractInvoice,
    AbstractOrder,
    AbstractPlan,
    AbstractPlanPricing,
    AbstractUserPlan,
)

User = get_user_model()
BillingInfo = AbstractBillingInfo.get_concrete_model()
Invoice = AbstractInvoice.get_concrete_model()
Order = AbstractOrder.get_concrete_model()
Plan = AbstractPlan.get_concrete_model()
PlanPricing = AbstractPlanPricing.get_concrete_model()
UserPlan = AbstractUserPlan.get_concrete_model()


class CustomerTestCase(TestCase):
    fixtures = ["initial_plan", "test_django-plans_auth", "test_django-plans_plans"]

    def setUp(self):
        self.user = baker.make(User, username="customer")
        self.plan_pricing = PlanPricing.objects.get(
            plan__name="Standard", pricing__period=30
        )
        self.client.force_login(self.user)

    def _order(self, **kwargs):
        fields = dict(
            user=self.user,
            plan=self.plan_pricing.plan,
            pricing=self.plan_pricing.pricing,
            amount=Decimal("10.00"),
            currency="EUR",
        )
        fields.update(kwargs)
        return Order.objects.create(**fields)


class OrderListTemplateTests(CustomerTestCase):
    def test_customer_without_orders_is_told_so(self):
        response = self.client.get(reverse("order_list"))

        self.assertContains(response, "You do not have any orders so far.")

    def test_more_than_ten_orders_are_split_into_pages(self):
        for _ in range(11):
            self._order()

        first = self.client.get(reverse("order_list"))
        second = self.client.get(reverse("order_list") + "?page=2")

        self.assertEqual(len(first.context["object_list"]), 10)
        self.assertContains(
            first,
            '<li><a class="pagination__next" href="?page=2&query=">&raquo;</a></li>',
            html=True,
            count=2,
        )
        self.assertEqual(len(second.context["object_list"]), 1)
        self.assertContains(
            second,
            '<li><a class="pagination__prev" href="?page=1&query=">&laquo;</a></li>',
            html=True,
            count=2,
        )


class OrderDetailTemplateTests(CustomerTestCase):
    def _get(self, order):
        return self.client.get(reverse("order", kwargs={"pk": order.pk}))

    def test_paid_order_shows_when_it_was_paid(self):
        order = self._order(
            status=Order.STATUS.COMPLETED,
            completed=make_aware(datetime(2024, 1, 15, 12)),
        )

        response = self._get(order)

        completed = date_format(localtime(order.completed), "DATETIME_FORMAT")
        self.assertContains(
            response,
            f'<p class="alert alert-success">Payment completed on: {completed}</p>',
            html=True,
        )

    def test_expired_order_cannot_be_paid_any_more(self):
        order = self._order()
        Order.objects.filter(pk=order.pk).update(created=now() - timedelta(days=15))

        response = self._get(order)

        self.assertContains(response, "This order is expired.")
        self.assertNotContains(
            response, reverse("fake_payments", kwargs={"pk": order.pk})
        )

    def test_invalid_order_asks_to_contact_customer_service(self):
        order = self._order(status=Order.STATUS.NOT_VALID)

        response = self._get(order)

        self.assertContains(
            response,
            '<p class="alert alert-danger">This order could not be processed as it '
            "is not valid. Please contact with customer service.</p>",
            html=True,
        )


class CreateOrderTemplateTests(CustomerTestCase):
    def test_customer_without_billing_info_is_told_no_invoice_will_be_issued(self):
        UserPlan.objects.filter(user=self.user).update(
            plan=Plan.objects.get(name="Free"), expire=None
        )

        response = self.client.get(
            reverse("create_order_plan", kwargs={"pk": self.plan_pricing.pk})
        )

        billing_info_url = (
            reverse("billing_info")
            + "?next="
            + reverse("create_order_plan", kwargs={"pk": self.plan_pricing.pk})
        )
        self.assertContains(
            response,
            '<p class="alert alert-info">Invoice will <b>not</b> be issued. If you '
            f'need an invoice please provide <a href="{billing_info_url}">billing '
            "data</a> before making an order.</p>",
            html=True,
        )


class PlanTableTemplateTests(CustomerTestCase):
    def test_customer_with_an_expired_plan_can_select_the_free_plan(self):
        UserPlan.objects.filter(user=self.user).update(
            plan=self.plan_pricing.plan, expire=localdate() - timedelta(days=1)
        )
        free_plan = Plan.objects.get(name="Free")

        response = self.client.get(reverse("pricing"))

        self.assertContains(
            response,
            f'<a href="{reverse("create_order_plan_change", kwargs={"pk": free_plan.pk})}"'
            ' class="change_plan">Select</a>',
            html=True,
        )


class InvoiceTemplateTests(CustomerTestCase):
    def _get(self, **invoice_fields):
        invoice = baker.make(
            "Invoice",
            order=self._order(),
            user=self.user,
            total=123,
            **invoice_fields,
        )
        return self.client.get(
            reverse("invoice_preview_html", kwargs={"pk": invoice.pk})
        )

    @override_settings(PLANS_INVOICE_LOGO_URL="https://example.com/logo.png")
    def test_invoice_shows_the_logo_buyer_vat_id_and_rebate(self):
        response = self._get(
            type=Invoice.INVOICE_TYPES.INVOICE,
            buyer_tax_number="DE123456789",
            rebate=Decimal("10"),
        )

        self.assertContains(
            response,
            '<img src="https://example.com/logo.png" alt="company logo">',
            html=True,
        )
        self.assertContains(
            response,
            '<p><label><span class="pl">Numer NIP:</span><span class="en">VAT ID'
            "</span></label> DE123456789</p>",
            html=True,
        )
        self.assertContains(response, '<td class="number">10.00&nbsp;%</td>', html=True)

    def test_proforma_says_it_is_not_an_invoice(self):
        response = self._get(type=Invoice.INVOICE_TYPES.PROFORMA)

        self.assertContains(
            response, '<span class="en">Order confirmation ID</span>', html=True
        )
        self.assertContains(
            response,
            '<span class="en">This document <strong>is not</strong> an invoice.'
            "</span>",
            html=True,
        )


@override_settings(
    PLANS_VALIDATORS={
        "MAX_FOO_COUNT": "plans.tests.test_validators.optional_max_foos_validator"
    }
)
class AccountActivationWarningTests(TestCase):
    def test_limits_not_required_to_activate_are_shown_as_warnings(self):
        user = baker.make(User)
        plan = baker.make("Plan")
        quota = baker.make("Quota", codename="MAX_FOO_COUNT")
        baker.make("PlanQuota", plan=plan, quota=quota, value=1)
        baker.make("UserPlan", user=user, plan=plan, active=False, expire=None)
        baker.make("foo.Foo", user=user, _quantity=2)
        self.client.force_login(user)

        response = self.client.get(reverse("account_activation"))

        self.assertContains(response, "<h1>Activation successful</h1>", html=True)
        self.assertEqual(
            [(m.level_tag, str(m)) for m in get_messages(response.wsgi_request)],
            [
                ("success", "Your account is now active"),
                ("warning", "Limit of foos exceeded. The limit is 1 items."),
            ],
        )


class BillingInfoFormTests(TestCase):
    def test_invalid_vat_id_is_reported_on_the_field(self):
        user = baker.make(User)
        self.client.force_login(user)

        response = self.client.post(
            reverse("billing_info"),
            {
                "country": "DE",
                "tax_number": "DE123456780",
                "name": "Customer GmbH",
                "street": "Hauptstr. 1",
                "city": "Berlin",
                "zipcode": "10115",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["form"].errors["tax_number"],
            [
                "VAT ID is not correct: The number's checksum or check digit is "
                "invalid."
            ],
        )
        self.assertFalse(BillingInfo.objects.filter(user=user).exists())
