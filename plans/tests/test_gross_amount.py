"""Tax-inclusive orders: ``Order.gross_amount`` and ``Order.net_from_gross``.

An order stores a net ``amount`` and a ``tax`` rate and derives the total by
multiplying and rounding. That cannot represent every tax-inclusive price:
at 21 % only 100 of every 121 gross cent values are reachable from a net
cent value. A subscription whose provider charges a fixed gross amount hits
the gaps as soon as the customer's tax rate changes. ``gross_amount`` stores
the charged total as the primary fact and ``net_from_gross`` splits it with
the coefficient method, so net + tax == total on the cent grid and the
invoice equals the charge.
"""

from datetime import datetime
from decimal import Decimal
from io import StringIO

from django.contrib.admin import site as admin_site
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase, TestCase

from plans.admin import OrderAdmin
from plans.base.models import AbstractOrder
from plans.models import BillingInfo, Invoice, Order, PlanPricing

User = get_user_model()

# (gross, tax rate, expected net): totals that no net cent value reaches at
# the given rate, taken from PayPal subscriptions renewed after a rate change.
UNREACHABLE_TOTALS = [
    (Decimal("14.89"), Decimal("21"), Decimal("12.31")),
    (Decimal("8.90"), Decimal("21"), Decimal("7.36")),
    (Decimal("18.48"), Decimal("25.5"), Decimal("14.73")),
    (Decimal("12.38"), Decimal("25.5"), Decimal("9.86")),
]


class OrderTotalTests(SimpleTestCase):
    def test_total_is_gross_amount_when_set(self):
        order = Order(
            amount=Decimal("12.31"), tax=Decimal("21"), gross_amount=Decimal("14.89")
        )

        self.assertEqual(order.total(), Decimal("14.89"))
        self.assertEqual(order.tax_total(), Decimal("2.58"))

    def test_total_is_computed_without_gross_amount(self):
        """The net-based total of the same order lands on 14.90: the cent the
        gross amount exists to represent."""
        order = Order(amount=Decimal("12.31"), tax=Decimal("21"))

        self.assertEqual(order.total(), Decimal("14.90"))
        self.assertEqual(order.tax_total(), Decimal("2.59"))

    def test_total_is_a_cent_decimal_whatever_the_field_holds(self):
        """An unsaved order may carry a float or a string; ``total()`` still
        returns a Decimal on the cent grid."""
        for raw in (14.89, "14.89", Decimal("14.890")):
            with self.subTest(raw=raw):
                order = Order(
                    amount=Decimal("12.31"), tax=Decimal("21"), gross_amount=raw
                )

                self.assertIsInstance(order.total(), Decimal)
                self.assertEqual(order.total(), Decimal("14.89"))
                self.assertEqual(str(order.total()), "14.89")

    def test_tax_total_is_zero_when_tax_not_applicable(self):
        order = Order(amount=Decimal("14.89"), tax=None, gross_amount=Decimal("14.89"))

        self.assertEqual(order.total(), Decimal("14.89"))
        self.assertEqual(order.tax_total(), Decimal("0.00"))


class NetFromGrossTests(SimpleTestCase):
    def test_unreachable_totals_split_to_the_cent(self):
        for gross, tax, expected_net in UNREACHABLE_TOTALS:
            with self.subTest(gross=gross, tax=tax):
                net = AbstractOrder.net_from_gross(gross, tax)

                self.assertEqual(net, expected_net)
                order = Order(amount=net, tax=tax, gross_amount=gross)
                self.assertEqual(order.total(), gross)
                self.assertEqual(order.amount + order.tax_total(), gross)

    def test_reachable_total_round_trips_to_its_net(self):
        self.assertEqual(
            AbstractOrder.net_from_gross(Decimal("14.90"), Decimal("21")),
            Decimal("12.31"),
        )
        self.assertEqual(
            Order(amount=Decimal("12.31"), tax=Decimal("21")).total(), Decimal("14.90")
        )

    def test_tax_not_applicable_returns_gross(self):
        self.assertEqual(
            AbstractOrder.net_from_gross(Decimal("14.89"), None), Decimal("14.89")
        )

    def test_zero_tax_returns_gross(self):
        self.assertEqual(
            AbstractOrder.net_from_gross(Decimal("14.89"), Decimal("0")),
            Decimal("14.89"),
        )

    def test_accepts_non_decimal_input(self):
        self.assertEqual(AbstractOrder.net_from_gross("10.00", 21), Decimal("8.26"))
        self.assertEqual(AbstractOrder.net_from_gross(10, "21.00"), Decimal("8.26"))

    def test_tax_amount_rounds_half_up(self):
        """0.12 at 60 %: tax 0.045 exactly; half-even would give 0.04."""
        self.assertEqual(
            AbstractOrder.net_from_gross(Decimal("0.12"), Decimal("60")),
            Decimal("0.07"),
        )

    def test_split_always_validates(self):
        """Every gross cent value at every common rate yields a net that
        passes the gross-amount validation, i.e. is within a cent of the
        net-based total."""
        rates = [Decimal(r) for r in ("0", "5", "19", "20", "21", "23", "25.5", "27")]
        for cents in range(1, 2001):
            gross = Decimal(cents) / 100
            for tax in rates:
                with self.subTest(gross=gross, tax=tax):
                    net = AbstractOrder.net_from_gross(gross, tax)
                    order = Order(amount=net, tax=tax, gross_amount=gross)
                    order.validate_gross_amount()
                    self.assertEqual(order.amount + order.tax_total(), gross)


class GrossAmountValidationTests(SimpleTestCase):
    def test_accepts_rounding_difference_below_one_cent(self):
        Order(
            amount=Decimal("12.31"), tax=Decimal("21"), gross_amount=Decimal("14.89")
        ).clean()

    def test_accepts_exact_total(self):
        Order(
            amount=Decimal("12.31"), tax=Decimal("21"), gross_amount=Decimal("14.90")
        ).clean()

    def test_accepts_empty_gross_amount(self):
        Order(amount=Decimal("12.31"), tax=Decimal("21")).clean()

    def test_rejects_different_price(self):
        order = Order(
            amount=Decimal("12.31"), tax=Decimal("21"), gross_amount=Decimal("15.00")
        )

        with self.assertRaises(ValidationError) as caught:
            order.clean()

        self.assertEqual(list(caught.exception.error_dict), ["gross_amount"])
        self.assertIn("expected about 14.90", str(caught.exception))

    def test_rejects_one_cent_off_from_gross_side(self):
        """A cent more than the rounded total is a different price, not
        rounding: 12.31 at 21 % is 14.895, so 14.91 is 1.5 cents away."""
        order = Order(
            amount=Decimal("12.31"), tax=Decimal("21"), gross_amount=Decimal("14.91")
        )

        with self.assertRaises(ValidationError):
            order.clean()

    def test_gross_must_equal_net_when_tax_not_applicable(self):
        Order(amount=Decimal("14.89"), tax=None, gross_amount=Decimal("14.89")).clean()

        with self.assertRaises(ValidationError):
            Order(
                amount=Decimal("14.88"), tax=None, gross_amount=Decimal("14.89")
            ).clean()

    def test_gross_requires_net_amount(self):
        with self.assertRaises(ValidationError) as caught:
            Order(amount=None, tax=Decimal("21"), gross_amount=Decimal("14.89")).clean()

        self.assertEqual(list(caught.exception.error_dict), ["gross_amount"])


class GrossAmountPersistenceTests(TestCase):
    fixtures = ["initial_plan", "test_django-plans_auth", "test_django-plans_plans"]

    def setUp(self):
        self.user = User.objects.get(username="test1")
        self.plan_pricing = PlanPricing.objects.first()

    def make_order(self, **kwargs):
        return Order(
            user=self.user,
            plan=self.plan_pricing.plan,
            pricing=self.plan_pricing.pricing,
            currency="EUR",
            **kwargs,
        )

    def test_save_persists_gross_amount(self):
        order = self.make_order(
            amount=Decimal("12.31"), tax=Decimal("21"), gross_amount=Decimal("14.89")
        )
        order.save()

        order = Order.objects.get(pk=order.pk)
        self.assertEqual(order.gross_amount, Decimal("14.89"))
        self.assertEqual(order.total(), Decimal("14.89"))
        self.assertEqual(order.tax_total(), Decimal("2.58"))

    def test_save_rejects_inconsistent_gross_amount(self):
        order = self.make_order(
            amount=Decimal("12.31"), tax=Decimal("21"), gross_amount=Decimal("15.00")
        )

        with self.assertRaises(ValidationError):
            order.save()

        self.assertFalse(Order.objects.filter(gross_amount=Decimal("15.00")).exists())

    def test_existing_orders_keep_net_based_total(self):
        order = self.make_order(amount=Decimal("12.31"), tax=Decimal("21"))
        order.save()

        order = Order.objects.get(pk=order.pk)
        self.assertIsNone(order.gross_amount)
        self.assertEqual(order.total(), Decimal("14.90"))


class GrossAmountInvoiceTests(TestCase):
    fixtures = ["initial_plan", "test_django-plans_auth", "test_django-plans_plans"]

    def setUp(self):
        self.user = User.objects.get(username="test1")
        BillingInfo.objects.get_or_create(user=self.user, defaults={"country": "US"})
        plan_pricing = PlanPricing.objects.first()
        self.order = Order.objects.create(
            user=self.user,
            plan=plan_pricing.plan,
            pricing=plan_pricing.pricing,
            amount=Decimal("12.31"),
            tax=Decimal("21"),
            gross_amount=Decimal("14.89"),
            currency="EUR",
            completed=datetime(2026, 9, 22, 12, 0),
        )

    def test_copy_from_order_uses_gross_total(self):
        invoice = Invoice()
        invoice.copy_from_order(self.order)

        self.assertEqual(invoice.total_net, Decimal("12.31"))
        self.assertEqual(invoice.tax, Decimal("21"))
        self.assertEqual(invoice.tax_total, Decimal("2.58"))
        self.assertEqual(invoice.total, Decimal("14.89"))
        self.assertEqual(invoice.total_net + invoice.tax_total, invoice.total)

    def test_created_invoice_and_credit_note_carry_the_charged_total(self):
        Invoice.create(self.order, Invoice.INVOICE_TYPES.INVOICE)
        invoice = Invoice.objects.get(
            order=self.order, type=Invoice.INVOICE_TYPES.INVOICE
        )

        self.assertEqual(invoice.total, Decimal("14.89"))
        self.assertEqual(invoice.tax_total, Decimal("2.58"))

        credit_note = invoice.cancel_invoice(reason="test")

        self.assertEqual(credit_note.total, Decimal("-14.89"))
        self.assertEqual(credit_note.total_net, Decimal("-12.31"))
        self.assertEqual(credit_note.tax_total, Decimal("-2.58"))

    def test_order_detail_table_shows_charged_total(self):
        html = render_to_string("plans/order_detail_table.html", {"order": self.order})

        self.assertIn("14.89 EUR", html)
        self.assertIn("2.58 EUR", html)
        self.assertNotIn("14.90", html)


class OrderAdminGrossAmountTests(TestCase):
    fixtures = ["initial_plan", "test_django-plans_auth", "test_django-plans_plans"]

    def setUp(self):
        self.user = User.objects.get(username="test1")
        self.plan_pricing = PlanPricing.objects.first()
        self.modeladmin = OrderAdmin(Order, admin_site)
        self.request = RequestFactory().get("/")
        self.request.user = self.user

    def test_gross_amount_and_totals_are_listed(self):
        self.assertIn("gross_amount", self.modeladmin.list_display)
        self.assertIn("total", self.modeladmin.list_display)
        self.assertIn("total", self.modeladmin.readonly_fields)
        self.assertIn("tax_total", self.modeladmin.readonly_fields)

    def test_gross_amount_is_editable_in_change_form(self):
        form_class = self.modeladmin.get_form(self.request)

        self.assertIn("gross_amount", form_class.base_fields)
        self.assertFalse(form_class.base_fields["gross_amount"].required)

    def test_change_form_rejects_inconsistent_gross_amount(self):
        form_class = self.modeladmin.get_form(self.request)
        form = form_class(
            data={
                "user": self.user.pk,
                "plan": self.plan_pricing.plan.pk,
                "pricing": self.plan_pricing.pricing.pk,
                "amount": "12.31",
                "tax": "21",
                "gross_amount": "15.00",
                "currency": "EUR",
                "status": Order.STATUS.NEW,
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("gross_amount", form.errors)

    def test_change_form_accepts_tax_inclusive_order(self):
        form_class = self.modeladmin.get_form(self.request)
        form = form_class(
            data={
                "user": self.user.pk,
                "plan": self.plan_pricing.plan.pk,
                "pricing": self.plan_pricing.pricing.pk,
                "amount": "12.31",
                "tax": "21",
                "gross_amount": "14.89",
                "currency": "EUR",
                "status": Order.STATUS.NEW,
            }
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_total_columns_read_from_the_order(self):
        order = Order(
            amount=Decimal("12.31"), tax=Decimal("21"), gross_amount=Decimal("14.89")
        )

        self.assertEqual(self.modeladmin.total(order), Decimal("14.89"))
        self.assertEqual(self.modeladmin.tax_total(order), Decimal("2.58"))

    def test_total_columns_are_empty_for_unsaved_blank_order(self):
        """The add form renders the read-only totals for an order without an
        amount yet."""
        self.assertIsNone(self.modeladmin.total(Order()))
        self.assertIsNone(self.modeladmin.tax_total(Order()))


class MigrationStateTests(TestCase):
    def test_models_match_migrations(self):
        out = StringIO()
        call_command("makemigrations", "plans", "--check", "--dry-run", stdout=out)

        self.assertIn("No changes detected", out.getvalue())
