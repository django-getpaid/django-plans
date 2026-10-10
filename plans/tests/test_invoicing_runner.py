from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from sequences.models import Sequence

from plans import invoicing
from plans.base.models import AbstractBillingInfo, AbstractInvoice, AbstractOrder
from plans.models import PlanPricing

User = get_user_model()
BillingInfo = AbstractBillingInfo.get_concrete_model()
Invoice = AbstractInvoice.get_concrete_model()
Order = AbstractOrder.get_concrete_model()

queued_jobs = []


def queue(job, *args):
    queued_jobs.append((job, args))


def run_queued_jobs():
    while queued_jobs:
        job, args = queued_jobs.pop(0)
        job(*args)


class InvoicingRunnerTests(TestCase):
    fixtures = ["initial_plan", "test_django-plans_auth", "test_django-plans_plans"]

    def setUp(self):
        self.user = User.objects.get(username="test1")
        BillingInfo.objects.get_or_create(user=self.user, defaults={"country": "US"})
        queued_jobs.clear()
        mail.outbox = []

    def make_order(self):
        plan_pricing = PlanPricing.objects.get(
            plan=self.user.userplan.plan, pricing__period=30
        )
        return Order.objects.create(
            user=self.user,
            pricing=plan_pricing.pricing,
            amount=100,
            plan=plan_pricing.plan,
        )

    def test_default_invoices_inside_the_order_transaction(self):
        order = self.make_order()
        order.complete_order()

        self.assertEqual(
            sorted(Invoice.objects.filter(order=order).values_list("type", flat=True)),
            [Invoice.INVOICE_TYPES.INVOICE, Invoice.INVOICE_TYPES.PROFORMA],
        )

    @override_settings(PLANS_INVOICING_RUNNER="plans.tests.test_invoicing_runner.queue")
    def test_runner_takes_invoicing_out_of_the_order_transaction(self):
        sequences = list(Sequence.objects.values_list("name", "last"))
        order = self.make_order()
        self.assertTrue(order.complete_order())

        self.assertFalse(Invoice.objects.filter(order=order).exists())
        self.assertEqual(list(Sequence.objects.values_list("name", "last")), sequences)
        self.assertEqual(
            queued_jobs,
            [
                (
                    invoicing.create_invoice,
                    (order.pk, Invoice.INVOICE_TYPES.PROFORMA),
                ),
                (
                    invoicing.create_invoice,
                    (order.pk, Invoice.INVOICE_TYPES.INVOICE),
                ),
            ],
        )

        run_queued_jobs()

        invoice = Invoice.objects.get(order=order, type=Invoice.INVOICE_TYPES.INVOICE)
        self.assertEqual(invoice.full_number, invoice.get_full_number())
        self.assertEqual(
            sum(invoice.full_number in message.body for message in mail.outbox), 1
        )

    @override_settings(PLANS_INVOICING_RUNNER="plans.tests.test_invoicing_runner.queue")
    def test_create_invoice_runs_again_without_a_second_invoice(self):
        order = self.make_order()
        order.complete_order()
        invoicing.create_invoice(order.pk, Invoice.INVOICE_TYPES.INVOICE)
        invoicing.create_invoice(order.pk, Invoice.INVOICE_TYPES.INVOICE)

        self.assertEqual(
            Invoice.objects.filter(
                order=order, type=Invoice.INVOICE_TYPES.INVOICE
            ).count(),
            1,
        )

    @override_settings(PLANS_INVOICING_RUNNER="plans.tests.test_invoicing_runner.queue")
    def test_jobs_of_an_order_deleted_meanwhile_do_nothing(self):
        order = self.make_order()
        order.complete_order()
        order_id = order.pk
        order.delete()

        with self.assertLogs("plans.invoicing", "WARNING") as logs:
            run_queued_jobs()

        self.assertFalse(Invoice.objects.filter(order_id=order_id).exists())
        self.assertEqual(
            logs.output,
            [
                f"WARNING:plans.invoicing:Order {order_id} no longer exists, "
                "no invoice created."
            ]
            * 2,
        )

    @override_settings(PLANS_INVOICING_RUNNER="plans.tests.test_invoicing_runner.queue")
    def test_the_email_job_of_an_invoice_deleted_meanwhile_does_nothing(self):
        order = self.make_order()
        order.complete_order()
        queued_jobs.clear()
        mail.outbox = []
        invoicing.create_invoice(order.pk, Invoice.INVOICE_TYPES.INVOICE)
        invoice = Invoice.objects.get(order=order)
        invoice_id = invoice.pk
        self.assertEqual(queued_jobs, [(invoicing.send_invoice_email, (invoice_id,))])
        invoice.delete()

        with self.assertLogs("plans.invoicing", "WARNING") as logs:
            run_queued_jobs()

        self.assertEqual(mail.outbox, [])
        self.assertEqual(
            logs.output,
            [
                f"WARNING:plans.invoicing:Invoice {invoice_id} no longer exists, "
                "no e-mail sent."
            ],
        )
