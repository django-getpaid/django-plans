from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from model_bakery import baker

User = get_user_model()


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
