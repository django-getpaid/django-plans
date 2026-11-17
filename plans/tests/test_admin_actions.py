from datetime import date, datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse
from django.utils.timezone import make_aware
from freezegun import freeze_time
from model_bakery import baker

from plans.base.models import (
    AbstractBillingInfo,
    AbstractInvoice,
    AbstractOrder,
    AbstractPlan,
    AbstractPlanPricing,
    AbstractRecurringUserPlan,
    AbstractUserPlan,
)

User = get_user_model()
BillingInfo = AbstractBillingInfo.get_concrete_model()
Invoice = AbstractInvoice.get_concrete_model()
Order = AbstractOrder.get_concrete_model()
Plan = AbstractPlan.get_concrete_model()
PlanPricing = AbstractPlanPricing.get_concrete_model()
RecurringUserPlan = AbstractRecurringUserPlan.get_concrete_model()
UserPlan = AbstractUserPlan.get_concrete_model()

INVOICE_CHANGELIST = "admin:plans_invoice_changelist"
ORDER_CHANGELIST = "admin:plans_order_changelist"


class AdminTestCase(TestCase):
    fixtures = ["initial_plan", "test_django-plans_auth", "test_django-plans_plans"]

    def setUp(self):
        self.admin_user = User.objects.get(username="test1")
        self.customer = baker.make(User, username="customer")
        baker.make(
            BillingInfo,
            user=self.customer,
            name="Customer Ltd",
            street="Main 1",
            zipcode="10001",
            city="New York",
            country="US",
            tax_number="",
        )
        self.plan_pricing = PlanPricing.objects.get(
            plan__name="Standard", pricing__period=30
        )
        self.client.force_login(self.admin_user)

    def _order(self, **kwargs):
        fields = dict(
            user=self.customer,
            plan=self.plan_pricing.plan,
            pricing=self.plan_pricing.pricing,
            amount=Decimal("100.00"),
            tax=Decimal("23.00"),
            currency="EUR",
        )
        fields.update(kwargs)
        return Order.objects.create(**fields)

    def _invoice(self):
        order = self._order(completed=make_aware(datetime(2024, 1, 15, 12)))
        return Invoice.create(order, Invoice.INVOICE_TYPES.INVOICE)

    def _messages(self, response):
        return [str(message) for message in get_messages(response.wsgi_request)]


class PartialCreditNoteActionTests(AdminTestCase):
    def _run_action(self, invoices, **data):
        payload = {
            "action": "create_partial_credit_note",
            "_selected_action": [invoice.pk for invoice in invoices],
        }
        payload.update(data)
        return self.client.post(reverse(INVOICE_CHANGELIST), payload)

    def test_form_is_prefilled_with_the_invoice_amounts(self):
        invoice = self._invoice()

        response = self._run_action([invoice])

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["invoice"], invoice)
        form = response.context["form"]
        self.assertEqual(form.initial["net_amount"], Decimal("100.00"))
        self.assertEqual(form.initial["tax_amount"], Decimal("23.00"))
        self.assertFalse(Invoice.credit_notes.filter(credit_note_for=invoice).exists())

    @freeze_time("2024-03-10 12:00:00")
    def test_apply_creates_a_credit_note_for_the_entered_amounts(self):
        invoice = self._invoice()

        response = self._run_action(
            [invoice],
            apply="1",
            net_amount="40.00",
            tax_amount="9.20",
            reason="Discount agreed by e-mail",
        )

        self.assertRedirects(response, reverse(INVOICE_CHANGELIST))
        credit_note = Invoice.credit_notes.get(credit_note_for=invoice)
        self.assertEqual(credit_note.total_net, Decimal("-40.00"))
        self.assertEqual(credit_note.tax_total, Decimal("-9.20"))
        self.assertEqual(credit_note.total, Decimal("-49.20"))
        self.assertEqual(credit_note.tax, invoice.tax)
        self.assertEqual(credit_note.currency, invoice.currency)
        self.assertEqual(credit_note.issued, date(2024, 3, 10))
        self.assertEqual(credit_note.payment_date, invoice.payment_date)
        self.assertEqual(credit_note.buyer_name, "Customer Ltd")
        self.assertEqual(
            credit_note.cancellation_reason, "Refund: Discount agreed by e-mail"
        )
        self.assertEqual(
            self._messages(response),
            [
                f"Partial credit note {credit_note.full_number} created "
                f"successfully for invoice {invoice.full_number}."
            ],
        )

    def test_negative_amounts_create_an_additional_charge(self):
        invoice = self._invoice()

        self._run_action(
            [invoice],
            apply="1",
            net_amount="0",
            tax_amount="-23.00",
            reason="VAT was not charged",
        )

        credit_note = Invoice.credit_notes.get(credit_note_for=invoice)
        self.assertEqual(credit_note.total_net, Decimal("0"))
        self.assertEqual(credit_note.tax_total, Decimal("23.00"))
        self.assertEqual(credit_note.total, Decimal("23.00"))
        self.assertEqual(
            credit_note.cancellation_reason, "Additional charge: VAT was not charged"
        )

    def test_missing_reason_shows_the_form_again_without_a_credit_note(self):
        invoice = self._invoice()

        response = self._run_action(
            [invoice], apply="1", net_amount="40.00", tax_amount="9.20", reason=""
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("reason", response.context["form"].errors)
        self.assertFalse(Invoice.credit_notes.filter(credit_note_for=invoice).exists())

    def test_more_than_one_invoice_is_refused(self):
        first, second = self._invoice(), self._invoice()

        response = self._run_action([first, second], follow=True)

        self.assertEqual(
            self._messages(response),
            ["Please select exactly one invoice to create a partial credit note."],
        )
        self.assertFalse(
            Invoice.credit_notes.filter(order__user=self.customer).exists()
        )

    def test_credit_note_cannot_get_a_partial_credit_note(self):
        credit_note = self._invoice().cancel_invoice(reason="Cancelled")

        response = self._run_action([credit_note], follow=True)

        self.assertEqual(
            self._messages(response),
            ["Only regular invoices can have partial credit notes."],
        )
        self.assertFalse(
            Invoice.credit_notes.filter(credit_note_for=credit_note).exists()
        )


class CancelInvoicesActionTests(AdminTestCase):
    def _cancel(self, invoices):
        return self.client.post(
            reverse(INVOICE_CHANGELIST),
            {
                "action": "cancel_selected_invoices",
                "_selected_action": [invoice.pk for invoice in invoices],
            },
            follow=True,
        )

    def test_cancel_issues_a_full_credit_note(self):
        invoice = self._invoice()

        response = self._cancel([invoice])

        credit_note = Invoice.credit_notes.get(credit_note_for=invoice)
        self.assertEqual(credit_note.total, -invoice.total)
        self.assertEqual(
            self._messages(response),
            [f"Invoice {invoice.full_number} cancelled successfully."],
        )

    def test_second_cancel_reports_an_error_and_issues_no_second_credit_note(self):
        invoice = self._invoice()
        self._cancel([invoice])

        response = self._cancel([invoice])

        self.assertEqual(
            Invoice.credit_notes.filter(credit_note_for=invoice).count(), 1
        )
        self.assertEqual(
            self._messages(response),
            [
                f"Could not cancel {invoice.full_number}: "
                "['This invoice has already been cancelled by a credit note.']"
            ],
        )

    def test_one_failure_does_not_stop_the_other_invoices(self):
        cancelled, other = self._invoice(), self._invoice()
        cancelled.cancel_invoice()

        self._cancel([cancelled, other])

        self.assertEqual(
            Invoice.credit_notes.filter(credit_note_for=cancelled).count(), 1
        )
        self.assertTrue(Invoice.credit_notes.filter(credit_note_for=other).exists())


class OrderActionsTests(AdminTestCase):
    def setUp(self):
        super().setUp()
        UserPlan.objects.filter(user=self.customer).update(
            plan=Plan.objects.get(name="Free"), expire=None
        )

    def _run(self, action, orders):
        return self.client.post(
            reverse(ORDER_CHANGELIST),
            {"action": action, "_selected_action": [order.pk for order in orders]},
        )

    @freeze_time("2024-01-15 12:00:00")
    def test_make_order_completed_extends_the_plan_and_invoices_the_order(self):
        order = self._order()

        self._run("make_order_completed", [order])

        order.refresh_from_db()
        self.assertEqual(order.status, Order.STATUS.COMPLETED)
        self.customer.userplan.refresh_from_db()
        self.assertEqual(self.customer.userplan.plan, self.plan_pricing.plan)
        self.assertEqual(self.customer.userplan.expire, date(2024, 2, 14))
        invoice = Invoice.invoices.get(order=order)
        self.assertEqual(invoice.total, Decimal("123.00"))

    @freeze_time("2024-01-15 12:00:00")
    def test_make_order_returned_reverts_the_plan_and_cancels_the_invoice(self):
        order = self._order()
        order.complete_order()
        invoice = Invoice.invoices.get(order=order)

        self._run("make_order_returned", [order])

        order.refresh_from_db()
        self.assertEqual(order.status, Order.STATUS.RETURNED)
        self.customer.userplan.refresh_from_db()
        self.assertEqual(self.customer.userplan.plan, Plan.objects.get(name="Free"))
        self.assertIsNone(self.customer.userplan.expire)
        credit_note = Invoice.credit_notes.get(credit_note_for=invoice)
        self.assertEqual(credit_note.total, Decimal("-123.00"))

    def test_make_order_invoice_skips_an_already_invoiced_order(self):
        invoice = self._invoice()

        self._run("make_order_invoice", [invoice.order])

        self.assertEqual(Invoice.invoices.filter(order=invoice.order).count(), 1)

    def test_make_order_invoice_invoices_a_completed_order(self):
        order = self._order(completed=make_aware(datetime(2024, 1, 15, 12)))

        self._run("make_order_invoice", [order])

        invoice = Invoice.invoices.get(order=order)
        self.assertEqual(invoice.total, Decimal("123.00"))
        self.assertEqual(invoice.buyer_name, "Customer Ltd")


class AdminPagesTests(AdminTestCase):
    """The admin pages of every registered plans model render for a superuser."""

    def test_changelists_render(self):
        self._invoice()
        baker.make(
            RecurringUserPlan,
            user_plan=self.customer.userplan,
            payment_provider="paypal",
            token_verified=True,
            renewal_triggered_by=RecurringUserPlan.RENEWAL_TRIGGERED_BY.TASK,
            pricing=self.plan_pricing.pricing,
        )
        for model in (
            "quota",
            "plan",
            "userplan",
            "pricing",
            "order",
            "billinginfo",
            "invoice",
        ):
            with self.subTest(model=model):
                response = self.client.get(reverse(f"admin:plans_{model}_changelist"))
                self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse("admin:plans_userplan_changelist"))
        self.assertContains(response, "paypal")

    def test_change_pages_link_to_the_user(self):
        invoice = self._invoice()
        user_change_url = reverse("admin:auth_user_change", args=(self.customer.pk,))
        for url in (
            reverse("admin:plans_userplan_change", args=(self.customer.userplan.pk,)),
            reverse(
                "admin:plans_billinginfo_change",
                args=(self.customer.billinginfo.pk,),
            ),
        ):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertContains(
                    response, f'<a href="{user_change_url}">customer</a>', html=True
                )
        for url in (
            reverse("admin:plans_invoice_change", args=(invoice.pk,)),
            reverse("admin:plans_order_change", args=(invoice.order.pk,)),
            reverse("admin:plans_plan_change", args=(invoice.order.plan.pk,)),
            reverse("admin:plans_pricing_change", args=(self.plan_pricing.pricing.pk,)),
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)
