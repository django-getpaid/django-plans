from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.timezone import localdate
from model_bakery import baker

from plans.base.models import AbstractPlan

User = get_user_model()
Plan = AbstractPlan.get_concrete_model()


def print_response(response):
    with open("response.html", "wb") as f:
        f.write(response.content)


class AccountActivationViewTests(TestCase):
    def test_get_active_plan(self):
        user = baker.make(User)
        baker.make("UserPlan", user=user)
        self.client.force_login(user)
        response = self.client.get(reverse("account_activation"))
        self.assertEqual(response.status_code, 404)

    def test_get(self):
        user = baker.make(User)
        baker.make("UserPlan", user=user, active=False)
        self.client.force_login(user)
        response = self.client.get(reverse("account_activation"))
        self.assertContains(response, "<h1>Activation successful</h1>", html=True)


class CurrentPlanViewTests(TestCase):
    def test_get(self):
        user = baker.make(User, username="Foo")
        baker.make("UserPlan", user=user, active=False)
        self.client.force_login(user)
        response = self.client.get(reverse("current_plan"))
        self.assertContains(response, "<h1>Your account</h1>", html=True)
        self.assertContains(response, "<dd>Foo</dd>", html=True)


class ChangePlanViewTests(TestCase):
    def test_get(self):
        user = baker.make(User, username="Foo")
        user_plan = baker.make("UserPlan", user=user, active=False)
        self.client.force_login(user)
        response = self.client.get(
            reverse("change_plan", kwargs={"pk": user_plan.plan.pk})
        )
        self.assertRedirects(response, "/plan/upgrade/")

    def test_post(self):
        user = baker.make(User, username="Foo")
        user_plan = baker.make("UserPlan", user=user, active=False)
        plan = baker.make("Plan", available=True, visible=True)
        self.client.force_login(user)
        response = self.client.post(reverse("change_plan", kwargs={"pk": plan.pk}))
        self.assertRedirects(response, "/plan/upgrade/")
        user_plan.refresh_from_db()
        self.assertEqual(user_plan.plan, plan)

    def make_paid_plan(self, monthly_price):
        plan = baker.make("Plan", available=True, visible=True)
        baker.make(
            "PlanPricing",
            plan=plan,
            pricing__period=30,
            price=Decimal(monthly_price),
        )
        return plan

    def post_change(self, user, plan):
        self.client.force_login(user)
        return self.client.post(reverse("change_plan", kwargs={"pk": plan.pk}))

    def test_post_free_plan_to_paid_plan_requires_payment(self):
        user = baker.make(User)
        free_plan = baker.make("Plan", default=True)
        user_plan = baker.make("UserPlan", user=user, plan=free_plan, expire=None)
        paid_plan = self.make_paid_plan("20.00")

        response = self.post_change(user, paid_plan)

        self.assertEqual(response.status_code, 403)
        user_plan.refresh_from_db()
        self.assertEqual(user_plan.plan, free_plan)
        self.assertIsNone(user_plan.expire)

    def test_post_downgrade_to_cheaper_plan_keeps_expiry(self):
        user = baker.make(User)
        expensive_plan = self.make_paid_plan("20.00")
        cheaper_plan = self.make_paid_plan("10.00")
        expire = localdate() + timedelta(days=10)
        user_plan = baker.make(
            "UserPlan", user=user, plan=expensive_plan, expire=expire
        )

        response = self.post_change(user, cheaper_plan)

        self.assertRedirects(response, "/plan/upgrade/")
        user_plan.refresh_from_db()
        self.assertEqual(user_plan.plan, cheaper_plan)
        self.assertEqual(user_plan.expire, expire)

    def test_post_expired_account_to_paid_plan_stays_expired(self):
        """With no days left there is nothing to charge for, and nothing to gain:
        the expiry stays in the past, so the default plan applies until an
        order extends the account."""
        user = baker.make(User)
        default_plan = baker.make("Plan", default=True)
        cheaper_plan = self.make_paid_plan("10.00")
        expensive_plan = self.make_paid_plan("20.00")
        expire = localdate() - timedelta(days=3)
        user_plan = baker.make("UserPlan", user=user, plan=cheaper_plan, expire=expire)

        response = self.post_change(user, expensive_plan)

        self.assertRedirects(response, "/plan/upgrade/")
        user_plan.refresh_from_db()
        self.assertEqual(user_plan.plan, expensive_plan)
        self.assertEqual(user_plan.expire, expire)
        self.assertEqual(
            Plan.get_current_plan(User.objects.get(pk=user.pk)), default_plan
        )

    def test_post_paid_plan_without_expiry_to_pricier_plan_requires_payment(self):
        user = baker.make(User)
        cheaper_plan = self.make_paid_plan("10.00")
        expensive_plan = self.make_paid_plan("20.00")
        user_plan = baker.make("UserPlan", user=user, plan=cheaper_plan, expire=None)

        response = self.post_change(user, expensive_plan)

        self.assertEqual(response.status_code, 403)
        user_plan.refresh_from_db()
        self.assertEqual(user_plan.plan, cheaper_plan)

    def test_post_paid_plan_without_expiry_to_cheaper_plan_keeps_no_expiry(self):
        user = baker.make(User)
        expensive_plan = self.make_paid_plan("20.00")
        cheaper_plan = self.make_paid_plan("10.00")
        user_plan = baker.make("UserPlan", user=user, plan=expensive_plan, expire=None)

        response = self.post_change(user, cheaper_plan)

        self.assertRedirects(response, "/plan/upgrade/")
        user_plan.refresh_from_db()
        self.assertEqual(user_plan.plan, cheaper_plan)
        self.assertIsNone(user_plan.expire)


class CreateOrderPlanChangeViewTests(TestCase):
    def test_get(self):
        user = baker.make(User, username="Foo")
        baker.make("UserPlan", user=user, active=False)
        plan = baker.make("Plan", available=True, visible=True, name="Foo plan")
        self.client.force_login(user)
        response = self.client.get(
            reverse("create_order_plan_change", kwargs={"pk": plan.pk})
        )
        self.assertContains(response, "<h1>Confirm order</h1>", html=True)
        self.assertContains(response, "<td>Plan Foo plan (upgrade) </td>", html=True)


class OrderViewTests(TestCase):
    def test_get(self):
        user = baker.make(User, username="Foo")
        order = baker.make("Order", user=user, plan__name="Foo plan")
        self.client.force_login(user)
        response = self.client.get(reverse("order", kwargs={"pk": order.pk}))
        self.assertContains(
            response, f"<h1>Order #{order.pk} (status: new)</h1>", html=True
        )
        self.assertContains(response, "<td>Plan Foo plan (upgrade) </td>", html=True)


class OrderListViewTests(TestCase):
    def test_get(self):
        user = baker.make(User, username="Foo")
        order = baker.make("Order", user=user, plan__name="Foo plan")
        self.client.force_login(user)
        response = self.client.get(reverse("order_list"))
        self.assertContains(response, "<h1>List of orders</h1>", html=True)
        self.assertContains(
            response, f'<a href="/plan/order/{order.pk}/">{order.pk}</a>', html=True
        )
        self.assertContains(
            response,
            f'<a href="/plan/order/{order.pk}/">Plan Foo plan (upgrade) </a>',
            html=True,
        )


class OrderPaymentReturnViewTests(TestCase):
    def test_success(self):
        user = baker.make(User, username="Foo")
        order = baker.make("Order", user=user, plan__name="Foo plan")
        self.client.force_login(user)
        response = self.client.get(
            reverse("order_payment_success", kwargs={"pk": order.pk})
        )
        self.assertRedirects(response, f"/plan/order/{order.pk}/")

    def test_failure(self):
        user = baker.make(User, username="Foo")
        order = baker.make("Order", user=user, plan__name="Foo plan")
        self.client.force_login(user)
        response = self.client.get(
            reverse("order_payment_failure", kwargs={"pk": order.pk})
        )
        self.assertRedirects(response, f"/plan/order/{order.pk}/")


class InvoiceDetailViewTests(TestCase):
    def test_get(self):
        user = baker.make(User, username="Foo")
        order = baker.make("Order", user=user, plan__name="Foo plan")
        invoice = baker.make("Invoice", order=order, user=user, total=123)
        self.client.force_login(user)
        response = self.client.get(
            reverse("invoice_preview_html", kwargs={"pk": invoice.pk})
        )
        self.assertContains(response, '<span class="en">Invoice ID</span>', html=True)
        self.assertContains(
            response, '<td class="number">123.00&nbsp;EUR</td>', html=True
        )

    def test_get_other_user(self):
        user_a = baker.make(User, username="Andy Aight")
        user_b = baker.make(User, username="Bob Bar")
        order_b = baker.make("Order", user=user_b, plan__name="Foo plan")
        invoice_b = baker.make("Invoice", order=order_b, user=user_b, total=123)
        # superusers can access all invoices
        self.assertFalse(user_a.is_superuser)
        self.assertFalse(user_b.is_superuser)
        # login as user_a and try to access user_b's invoice
        self.client.force_login(user_a)
        response = self.client.get(
            reverse("invoice_preview_html", kwargs={"pk": invoice_b.pk})
        )
        self.assertContains(response, "<h1>Invoice Not Found</h1>", status_code=404)
        # login as user B and ensure the invoice is available
        self.client.force_login(user_b)
        response = self.client.get(
            reverse("invoice_preview_html", kwargs={"pk": invoice_b.pk})
        )
        self.assertContains(response, '<span class="en">Invoice ID</span>', html=True)


class FakePaymentViewTests(TestCase):
    def test_get(self):
        user = baker.make(User, username="Foo")
        order = baker.make("Order", user=user, plan__name="Foo plan")
        self.client.force_login(user)
        response = self.client.get(reverse("fake_payments", kwargs={"pk": order.pk}))
        self.assertContains(
            response, "This view is accessible only in debug mode.", status_code=403
        )

    @override_settings(DEBUG=True)
    def test_get_debug(self):
        user = baker.make(User, username="Foo")
        order = baker.make("Order", user=user, plan__name="Foo plan")
        self.client.force_login(user)
        response = self.client.get(reverse("fake_payments", kwargs={"pk": order.pk}))
        self.assertContains(response, "<h1>FakePayments™</h1>", html=True)

    @override_settings(DEBUG=True)
    def test_post_completed(self):
        user = baker.make(User, username="Foo")
        baker.make("UserPlan", user=user, active=False)
        order = baker.make("Order", user=user, plan__name="Foo plan")
        self.client.force_login(user)
        response = self.client.post(
            reverse("fake_payments", kwargs={"pk": order.pk}), {"status": 2}
        )
        self.assertRedirects(
            response,
            f"/plan/order/{order.pk}/payment/success/",
            fetch_redirect_response=False,
        )

    @override_settings(DEBUG=True)
    def test_post_failed(self):
        user = baker.make(User, username="Foo")
        baker.make("UserPlan", user=user, active=False)
        order = baker.make("Order", user=user, plan__name="Foo plan")
        self.client.force_login(user)
        response = self.client.post(
            reverse("fake_payments", kwargs={"pk": order.pk}), {"status": 4}
        )
        self.assertRedirects(
            response,
            f"/plan/order/{order.pk}/payment/failure/",
            fetch_redirect_response=False,
        )
