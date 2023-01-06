import random
from datetime import date, timedelta
from decimal import Decimal
from io import StringIO
from unittest import mock
from unittest.mock import patch

import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.core import mail
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.core.management import call_command
from django.db import transaction
from django.db.models import Q
from django.test import (RequestFactory, TestCase, TransactionTestCase,
                         override_settings)
from django.urls import reverse
from django_concurrent_tests.helpers import call_concurrently
from freezegun import freeze_time
from internet_sabotage import no_connection
from model_bakery import baker

from plans import tasks
from plans.base.models import (AbstractBillingInfo, AbstractInvoice,
                               AbstractOrder, AbstractPlan,
                               AbstractPlanPricing, AbstractUserPlan)
from plans.plan_change import PlanChangePolicy, StandardPlanChangePolicy
from plans.quota import get_user_quota
from plans.taxation.eu import EUTaxationPolicy
from plans.validators import ModelCountValidator
from plans.views import CreateOrderView

User = get_user_model()
BillingInfo = AbstractBillingInfo.get_concrete_model()
PlanPricing = AbstractPlanPricing.get_concrete_model()
Invoice = AbstractInvoice.get_concrete_model()
Order = AbstractOrder.get_concrete_model()
Plan = AbstractPlan.get_concrete_model()
UserPlan = AbstractUserPlan.get_concrete_model()


class PlansTestCase(TestCase):
    fixtures = ['initial_plan', 'test_django-plans_auth', 'test_django-plans_plans']

    def setUp(self):
        mail.outbox = []

    def test_create_userplans_command(self):
        """ Test that create_userplans command creates userplan for users that doesn't have it """
        u = User.objects.get(username='test1')
        UserPlan.objects.all().delete()
        with self.assertRaises(UserPlan.DoesNotExist):
            u.userplan
        u.refresh_from_db()
        out = StringIO()
        call_command('create_userplans', stdout=out)
        self.assertIn('2 user plans was created', out.getvalue())
        default_plan = Plan.objects.get(pk=1)
        self.assertEqual(u.userplan.plan, default_plan)

    def test_create_userplans(self):
        """ Test that create_for_users_without_plan method """
        u = User.objects.get(username='test1')
        UserPlan.objects.all().delete()
        with self.assertRaises(UserPlan.DoesNotExist):
            u.userplan
        u.refresh_from_db()
        created_plans = UserPlan.create_for_users_without_plan()
        self.assertEqual(created_plans.count(), 2)
        default_plan = Plan.objects.get(pk=1)
        self.assertEqual(u.userplan.plan, default_plan)

    def test_get_user_quota(self):
        u = User.objects.get(username='test1')
        self.assertEqual(get_user_quota(u),
                         {u'CUSTOM_WATERMARK': 1, u'MAX_GALLERIES_COUNT': 3, u'MAX_PHOTOS_PER_GALLERY': None})

    def test_get_user_quota_expired_no_default(self):
        u = User.objects.get(username='test1')
        u.userplan.expire = date.today() - timedelta(days=5)
        Plan.get_default_plan().delete()
        with self.assertRaises(ValidationError):
            get_user_quota(u)

    def test_get_user_quota_expired_free_plan(self):
        u = User.objects.get(username='test1')
        u.userplan.expire = date.today() - timedelta(days=5)
        with self.assertRaises(ValidationError):
            get_user_quota(u)

    def test_get_plan_quota(self):
        u = User.objects.get(username='test1')
        p = u.userplan.plan
        self.assertEqual(p.get_quota_dict(),
                         {u'CUSTOM_WATERMARK': 1, u'MAX_GALLERIES_COUNT': 3, u'MAX_PHOTOS_PER_GALLERY': None})

    def test_extend_account_same_plan_future(self):
        u = User.objects.get(username='test1')
        u.userplan.expire = date.today() + timedelta(days=50)
        u.userplan.active = False
        u.userplan.save()
        plan_pricing = PlanPricing.objects.get(plan=u.userplan.plan, pricing__period=30)
        u.userplan.extend_account(plan_pricing.plan, plan_pricing.pricing)
        self.assertEqual(u.userplan.expire,
                         date.today() + timedelta(days=50) + timedelta(days=plan_pricing.pricing.period))
        self.assertEqual(u.userplan.plan, plan_pricing.plan)
        self.assertEqual(u.userplan.active, True)
        self.assertEqual(len(mail.outbox), 1)

    def test_extend_account_same_plan_before(self):
        u = User.objects.get(username='test1')
        u.userplan.expire = date.today() - timedelta(days=50)
        u.userplan.active = False
        u.userplan.save()
        plan_pricing = PlanPricing.objects.get(plan=u.userplan.plan, pricing__period=30)
        u.userplan.extend_account(plan_pricing.plan, plan_pricing.pricing)
        self.assertEqual(u.userplan.expire, date.today() + timedelta(days=plan_pricing.pricing.period))
        self.assertEqual(u.userplan.plan, plan_pricing.plan)
        self.assertEqual(u.userplan.active, True)
        self.assertEqual(len(mail.outbox), 1)

    def test_extend_account_other(self):
        """
        Tests extending expired account with other Plan that user had before:
        Tests if expire date is set correctly
        Tests if mail has been send
        Tests if account has been activated
        """
        u = User.objects.get(username='test1')
        u.userplan.expire = date.today() - timedelta(days=50)
        u.userplan.active = False
        u.userplan.save()
        plan_pricing = PlanPricing.objects.filter(~Q(plan=u.userplan.plan) & Q(pricing__period=30))[0]
        u.userplan.extend_account(plan_pricing.plan, plan_pricing.pricing)
        self.assertEqual(u.userplan.expire, date.today() + timedelta(days=plan_pricing.pricing.period))
        self.assertEqual(u.userplan.plan, plan_pricing.plan)
        self.assertEqual(u.userplan.active, True)
        self.assertEqual(len(mail.outbox), 1)

    @freeze_time("2012-01-14")
    def test_extend_account_other_expire_none(self):
        """
        Tests extending expired=None account with other Plan that user had before and is expired:
        Tests if expire stays None
        Tests if mail has been send
        Tests if account stays activated
        """
        u = User.objects.get(username='test1')
        u.userplan.expire = None
        u.userplan.active = False
        u.userplan.save()
        plan_pricing = PlanPricing.objects.filter(~Q(plan=u.userplan.plan) & Q(pricing__period=30))[0]
        default_plan = Plan.objects.get(pk=1)
        u.userplan.extend_account(plan_pricing.plan, plan_pricing.pricing)
        self.assertEqual(u.userplan.expire, date(2012, 2, 13))
        self.assertEqual(u.userplan.plan, default_plan)
        self.assertEqual(u.userplan.active, True)
        self.assertEqual(len(mail.outbox), 1)

    def test_extend_account_other_expire_future(self):
        """
        Tests extending active account with other Plan that user had before:
        Tests if expire date stays the same
        Tests if mail has not been send
        Tests if account has not been activated
        """
        u = User.objects.get(username='test1')
        u.userplan.expire = date.today() + timedelta(days=5)
        u.userplan.active = False
        u.userplan.save()
        plan_pricing = PlanPricing.objects.filter(~Q(plan=u.userplan.plan) & Q(pricing__period=30))[0]
        default_plan = Plan.objects.get(pk=1)
        u.userplan.extend_account(plan_pricing.plan, plan_pricing.pricing)
        self.assertEqual(u.userplan.expire, date.today() + timedelta(days=5))
        self.assertEqual(u.userplan.plan, default_plan)
        self.assertEqual(u.userplan.active, False)
        self.assertEqual(len(mail.outbox), 0)

    def test_expire_account(self):
        u = User.objects.get(username='test1')
        u.userplan.expire = date.today() + timedelta(days=50)
        u.userplan.active = True
        u.userplan.save()
        u.userplan.expire_account()
        self.assertEqual(u.userplan.active, False)
        self.assertEqual(len(mail.outbox), 1)

    def test_remind_expire(self):
        u = User.objects.get(username='test1')
        u.userplan.expire = date.today() + timedelta(days=14)
        u.userplan.active = True
        u.userplan.save()
        u.userplan.remind_expire_soon()
        self.assertEqual(u.userplan.active, True)
        self.assertEqual(len(mail.outbox), 1)

    def test_disable_emails(self):
        with self.settings(SEND_PLANS_EMAILS=False):
            # Re-run the remind_expire test, but look for 0 emails sent
            u = User.objects.get(username='test1')
            u.userplan.expire = date.today() + timedelta(days=14)
            u.userplan.active = True
            u.userplan.save()
            u.userplan.remind_expire_soon()
            self.assertEqual(u.userplan.active, True)
            self.assertEqual(len(mail.outbox), 0)

    def test_switch_to_free_no_expiry(self):
        """
        Tests switching to a free Plan and checks that their expiry is cleared
        Tests if expire date is set correctly
        Tests if mail has been send
        Tests if account has been activated
        """
        u = User.objects.get(username='test1')
        u.userplan.expire = date.today() + timedelta(days=14)
        self.assertIsNotNone(u.userplan.expire)

        plan = Plan.objects.get(name="Free")
        self.assertTrue(plan.is_free())
        self.assertNotEqual(u.userplan.plan, plan)

        # Switch to Free Plan
        u.userplan.extend_account(plan, None)
        self.assertEqual(u.userplan.plan, plan)
        self.assertIsNone(u.userplan.expire)
        self.assertEqual(u.userplan.active, True)

    def test_switch_from_free_set_expiry(self):
        """
        Tests switching from a free Plan and should set the expiry date
        Tests if expire date is set correctly
        Tests if mail has been send
        Tests if account has been activated
        """
        u = User.objects.get(username='test1')
        u.userplan.expire = None
        u.userplan.plan = Plan.objects.get(name="Free")
        u.userplan.save()
        self.assertIsNone(u.userplan.expire)
        self.assertTrue(u.userplan.plan.is_free())

        plan = Plan.objects.get(name="Standard")
        self.assertFalse(plan.is_free())
        self.assertNotEqual(u.userplan.plan, plan)
        plan_pricing = PlanPricing.objects.filter(Q(plan=plan) & Q(pricing__period=30))[0]

        # Switch to Standard Plan
        u.userplan.extend_account(plan, plan_pricing.pricing)
        self.assertEqual(u.userplan.plan, plan)
        self.assertIsNotNone(u.userplan.expire)
        self.assertEqual(u.userplan.active, True)


class TestInvoice(TestCase):
    fixtures = ['initial_plan', 'test_django-plans_auth', 'test_django-plans_plans']

    def test_get_full_number(self):
        i = Invoice()
        i.number = 123
        i.issued = date(2010, 5, 30)
        self.assertEqual(i.get_full_number(), "123/FV/05/2010")

    def test_get_full_number_type1(self):
        i = Invoice()
        i.type = Invoice.INVOICE_TYPES.INVOICE
        i.number = 123
        i.issued = date(2010, 5, 30)
        self.assertEqual(i.get_full_number(), "123/FV/05/2010")

    def test_get_full_number_type2(self):
        i = Invoice()
        i.type = Invoice.INVOICE_TYPES.DUPLICATE
        i.number = 123
        i.issued = date(2010, 5, 30)
        self.assertEqual(i.get_full_number(), "123/FV/05/2010")

    def test_get_full_number_type3(self):
        i = Invoice()
        i.type = Invoice.INVOICE_TYPES.PROFORMA
        i.number = 123
        i.issued = date(2010, 5, 30)
        self.assertEqual(i.get_full_number(), "123/PF/05/2010")

    def test_get_full_number_with_settings(self):
        settings.PLANS_INVOICE_NUMBER_FORMAT = "{{ invoice.issued|date:'Y' }}." \
            "{{ invoice.number }}.{{ invoice.issued|date:'m' }}"
        i = Invoice()
        i.number = 123
        i.issued = date(2010, 5, 30)
        self.assertEqual(i.get_full_number(), "2010.123.05")

    def test_set_issuer_invoice_data_raise(self):
        issdata = settings.PLANS_INVOICE_ISSUER
        del settings.PLANS_INVOICE_ISSUER
        i = Invoice()
        self.assertRaises(ImproperlyConfigured, i.set_issuer_invoice_data)
        settings.PLANS_INVOICE_ISSUER = issdata

    def test_set_issuer_invoice_data(self):
        i = Invoice()
        i.set_issuer_invoice_data()
        self.assertEqual(i.issuer_name, settings.PLANS_INVOICE_ISSUER['issuer_name'])
        self.assertEqual(i.issuer_street, settings.PLANS_INVOICE_ISSUER['issuer_street'])
        self.assertEqual(i.issuer_zipcode, settings.PLANS_INVOICE_ISSUER['issuer_zipcode'])
        self.assertEqual(i.issuer_city, settings.PLANS_INVOICE_ISSUER['issuer_city'])
        self.assertEqual(i.issuer_country, settings.PLANS_INVOICE_ISSUER['issuer_country'])
        self.assertEqual(i.issuer_tax_number, settings.PLANS_INVOICE_ISSUER['issuer_tax_number'])

    def set_buyer_invoice_data(self):
        i = Invoice()
        u = User.objects.get(username='test1')
        i.set_buyer_invoice_data(u.billinginfo)
        self.assertEqual(i.buyer_name, u.billinginfo.name)
        self.assertEqual(i.buyer_street, u.billinginfo.street)
        self.assertEqual(i.buyer_zipcode, u.billinginfo.zipcode)
        self.assertEqual(i.buyer_city, u.billinginfo.city)
        self.assertEqual(i.buyer_country, u.billinginfo.country)
        self.assertEqual(i.buyer_tax_number, u.billinginfo.tax_number)
        self.assertEqual(i.buyer_name, u.billinginfo.shipping_name)
        self.assertEqual(i.buyer_street, u.billinginfo.shipping_street)
        self.assertEqual(i.buyer_zipcode, u.billinginfo.shipping_zipcode)
        self.assertEqual(i.buyer_city, u.billinginfo.shipping_city)
        self.assertEqual(i.buyer_country, u.billinginfo.shipping_country)

    def test_invoice_number(self):
        settings.PLANS_INVOICE_NUMBER_FORMAT = "{{ invoice.number }}/{% if " \
            "invoice.type == invoice.INVOICE_TYPES.PROFORMA %}PF{% else %}FV" \
            "{% endif %}/{{ invoice.issued|date:'m/Y' }}"
        o = Order.objects.all()[0]
        day = date(2010, 5, 3)
        i = Invoice(issued=day, selling_date=day, payment_date=day)
        i.copy_from_order(o)
        i.set_issuer_invoice_data()
        i.set_buyer_invoice_data(o.user.billinginfo)
        i.clean()
        i.save()

        self.assertEqual(i.number, 1)
        self.assertEqual(i.full_number, '1/FV/05/2010')

    def test_invoice_number_daily(self):
        settings.PLANS_INVOICE_NUMBER_FORMAT = "{{ invoice.number }}/{% if " \
            "invoice.type == invoice.INVOICE_TYPES.PROFORMA %}PF{% else %}FV" \
            "{% endif %}/{{ invoice.issued|date:'d/m/Y' }}"
        settings.PLANS_INVOICE_COUNTER_RESET = Invoice.NUMBERING.DAILY

        user = User.objects.get(username='test1')
        plan_pricing = PlanPricing.objects.all()[0]
        tax = getattr(settings, "PLANS_TAX")
        currency = getattr(settings, "PLANS_CURRENCY")
        o1 = Order(user=user, plan=plan_pricing.plan,
                   pricing=plan_pricing.pricing, amount=plan_pricing.price,
                   tax=tax, currency=currency)
        o1.save()

        o2 = Order(user=user, plan=plan_pricing.plan,
                   pricing=plan_pricing.pricing, amount=plan_pricing.price,
                   tax=tax, currency=currency)
        o2.save()

        o3 = Order(user=user, plan=plan_pricing.plan,
                   pricing=plan_pricing.pricing, amount=plan_pricing.price,
                   tax=tax, currency=currency)
        o3.save()

        day = date(2001, 5, 3)
        i1 = Invoice(issued=day, selling_date=day, payment_date=day)
        i1.copy_from_order(o1)
        i1.set_issuer_invoice_data()
        i1.set_buyer_invoice_data(o1.user.billinginfo)
        i1.clean()
        i1.save()

        i2 = Invoice(issued=day, selling_date=day, payment_date=day)
        i2.copy_from_order(o2)
        i2.set_issuer_invoice_data()
        i2.set_buyer_invoice_data(o2.user.billinginfo)
        i2.clean()
        i2.save()

        day = date(2001, 5, 4)
        i3 = Invoice(issued=day, selling_date=day, payment_date=day)
        i3.copy_from_order(o1)
        i3.set_issuer_invoice_data()
        i3.set_buyer_invoice_data(o1.user.billinginfo)
        i3.clean()
        i3.save()

        self.assertEqual(i1.full_number, "1/FV/03/05/2001")
        self.assertEqual(i2.full_number, "2/FV/03/05/2001")
        self.assertEqual(i3.full_number, "1/FV/04/05/2001")

    def test_invoice_number_monthly(self):
        settings.PLANS_INVOICE_NUMBER_FORMAT = "{{ invoice.number }}/{% if " \
            "invoice.type == invoice.INVOICE_TYPES.PROFORMA %}PF{% else %}FV" \
            "{% endif %}/{{ invoice.issued|date:'m/Y' }}"
        settings.PLANS_INVOICE_COUNTER_RESET = Invoice.NUMBERING.MONTHLY

        user = User.objects.get(username='test1')
        plan_pricing = PlanPricing.objects.all()[0]
        tax = getattr(settings, "PLANS_TAX")
        currency = getattr(settings, "PLANS_CURRENCY")
        o1 = Order(user=user, plan=plan_pricing.plan,
                   pricing=plan_pricing.pricing, amount=plan_pricing.price,
                   tax=tax, currency=currency)
        o1.save()

        o2 = Order(user=user, plan=plan_pricing.plan,
                   pricing=plan_pricing.pricing, amount=plan_pricing.price,
                   tax=tax, currency=currency)
        o2.save()

        o3 = Order(user=user, plan=plan_pricing.plan,
                   pricing=plan_pricing.pricing, amount=plan_pricing.price,
                   tax=tax, currency=currency)
        o3.save()

        day = date(2002, 5, 3)
        i1 = Invoice(issued=day, selling_date=day, payment_date=day)
        i1.copy_from_order(o1)
        i1.set_issuer_invoice_data()
        i1.set_buyer_invoice_data(o1.user.billinginfo)
        i1.clean()
        i1.save()

        day = date(2002, 5, 13)
        i2 = Invoice(issued=day, selling_date=day, payment_date=day)
        i2.copy_from_order(o2)
        i2.set_issuer_invoice_data()
        i2.set_buyer_invoice_data(o2.user.billinginfo)
        i2.clean()
        i2.save()

        day = date(2002, 6, 1)
        i3 = Invoice(issued=day, selling_date=day, payment_date=day)
        i3.copy_from_order(o1)
        i3.set_issuer_invoice_data()
        i3.set_buyer_invoice_data(o1.user.billinginfo)
        i3.clean()
        i3.save()

        self.assertEqual(i1.full_number, "1/FV/05/2002")
        self.assertEqual(i2.full_number, "2/FV/05/2002")
        self.assertEqual(i3.full_number, "1/FV/06/2002")

    def test_invoice_number_annually(self):
        settings.PLANS_INVOICE_NUMBER_FORMAT = "{{ invoice.number }}/{% if " \
            "invoice.type == invoice.INVOICE_TYPES.PROFORMA %}PF{% else %}FV" \
            "{% endif %}/{{ invoice.issued|date:'Y' }}"
        settings.PLANS_INVOICE_COUNTER_RESET = Invoice.NUMBERING.ANNUALLY

        user = User.objects.get(username='test1')
        plan_pricing = PlanPricing.objects.all()[0]
        tax = getattr(settings, "PLANS_TAX")
        currency = getattr(settings, "PLANS_CURRENCY")
        o1 = Order(user=user, plan=plan_pricing.plan,
                   pricing=plan_pricing.pricing, amount=plan_pricing.price,
                   tax=tax, currency=currency)
        o1.save()

        o2 = Order(user=user, plan=plan_pricing.plan,
                   pricing=plan_pricing.pricing, amount=plan_pricing.price,
                   tax=tax, currency=currency)
        o2.save()

        o3 = Order(user=user, plan=plan_pricing.plan,
                   pricing=plan_pricing.pricing, amount=plan_pricing.price,
                   tax=tax, currency=currency)
        o3.save()

        day = date(1991, 5, 3)
        i1 = Invoice(issued=day, selling_date=day, payment_date=day)
        i1.copy_from_order(o1)
        i1.set_issuer_invoice_data()
        i1.set_buyer_invoice_data(o1.user.billinginfo)
        i1.clean()
        i1.save()

        day = date(1991, 7, 13)
        i2 = Invoice(issued=day, selling_date=day, payment_date=day)
        i2.copy_from_order(o2)
        i2.set_issuer_invoice_data()
        i2.set_buyer_invoice_data(o2.user.billinginfo)
        i2.clean()
        i2.save()

        day = date(1992, 6, 1)
        i3 = Invoice(issued=day, selling_date=day, payment_date=day)
        i3.copy_from_order(o1)
        i3.set_issuer_invoice_data()
        i3.set_buyer_invoice_data(o1.user.billinginfo)
        i3.clean()
        i3.save()

        self.assertEqual(i1.full_number, "1/FV/1991")
        self.assertEqual(i2.full_number, "2/FV/1991")
        self.assertEqual(i3.full_number, "1/FV/1992")

    def test_invoice_number_custom(self):
        settings.PLANS_INVOICE_NUMBER_FORMAT = "{{ invoice.number }}/{% if " \
            "invoice.type == invoice.INVOICE_TYPES.PROFORMA %}PF{% else %}FV" \
            "{% endif %}/{{ invoice.issued|date:'Y' }}"

        def plans_invoice_counter_reset_function(invoice):
            from plans.base.models import get_initial_number

            older_invoices = Invoice.objects.filter(
                type=invoice.type,
                issued__year=invoice.issued.year,
                issued__month=invoice.issued.month,
                currency=invoice.currency,
            )
            sequence_name = f"{invoice.issued.year}_{invoice.issued.month}_{invoice.currency}"
            return sequence_name, get_initial_number(older_invoices)

        settings.PLANS_INVOICE_COUNTER_RESET = plans_invoice_counter_reset_function

        user = User.objects.get(username='test1')
        plan_pricing = PlanPricing.objects.all()[0]
        tax = getattr(settings, "PLANS_TAX")
        currency = getattr(settings, "PLANS_CURRENCY")
        currency1 = 'CZK'
        o1 = Order(user=user, plan=plan_pricing.plan,
                   pricing=plan_pricing.pricing, amount=plan_pricing.price,
                   tax=tax, currency=currency)
        o1.save()

        o2 = Order(user=user, plan=plan_pricing.plan,
                   pricing=plan_pricing.pricing, amount=plan_pricing.price,
                   tax=tax, currency=currency1)
        o2.save()

        o3 = Order(user=user, plan=plan_pricing.plan,
                   pricing=plan_pricing.pricing, amount=plan_pricing.price,
                   tax=tax, currency=currency)
        o3.save()

        day = date(1991, 7, 13)
        i1 = Invoice(issued=day, selling_date=day, payment_date=day)
        i1.copy_from_order(o1)
        i1.set_issuer_invoice_data()
        i1.set_buyer_invoice_data(o1.user.billinginfo)
        i1.clean()
        i1.save()

        day = date(1991, 7, 13)
        i2 = Invoice(issued=day, selling_date=day, payment_date=day)
        i2.copy_from_order(o2)
        i2.set_issuer_invoice_data()
        i2.set_buyer_invoice_data(o2.user.billinginfo)
        i2.clean()
        i2.save()

        day = date(1991, 7, 13)
        i3 = Invoice(issued=day, selling_date=day, payment_date=day)
        i3.copy_from_order(o1)
        i3.set_issuer_invoice_data()
        i3.set_buyer_invoice_data(o1.user.billinginfo)
        i3.clean()
        i3.save()

        self.assertEqual(i1.full_number, "1/FV/1991")
        self.assertEqual(i2.full_number, "1/FV/1991")
        self.assertEqual(i3.full_number, "2/FV/1991")

    def test_set_order(self):
        o = Order.objects.all()[0]

        i = Invoice()
        i.copy_from_order(o)

        self.assertEqual(i.order, o)
        self.assertEqual(i.user, o.user)
        self.assertEqual(i.total_net, o.amount)
        self.assertEqual(i.unit_price_net, o.amount)
        self.assertEqual(i.total, o.total())
        self.assertEqual(i.tax, o.tax)
        self.assertEqual(i.tax_total, o.total() - o.amount)
        self.assertEqual(i.currency, o.currency)


@transaction.atomic
def complete_order():
    user = User.objects.get(username='test1')

    plan_pricing = PlanPricing.objects.all()[0]
    o1 = Order(user=user, plan=plan_pricing.plan,
               pricing=plan_pricing.pricing, amount=plan_pricing.price,
               )
    o1.save()
    with freeze_time(random.choice(["2012-01-14", "2012-02-14"])):
        o1.complete_order()


def complete_concrete_order(order_id):
    order = Order.objects.get(id=order_id)
    order.complete_order()


class ConcurrentTestInvoice(TransactionTestCase):
    fixtures = ['initial_plan', 'test_django-plans_auth', 'test_django-plans_plans']

    def test_invoice_number_monthly_duplicity(self):
        """
        Test for problem where two simultaneously created invoices had duplicate number
        """
        call_concurrently(15, complete_order)
        invoices = Invoice.objects.filter(type=Invoice.INVOICE_TYPES.INVOICE).order_by("issued", "number")

        first_december_number = 0
        for i in range(1, 15):
            invoice = invoices[i - 1]
            if invoice.issued.month == 2 and first_december_number == 0:
                first_december_number = i - 1
            invoice_number = i - first_december_number
            self.assertEqual(invoice.number, invoice_number)
            self.assertEqual(invoice.full_number, f"{invoice_number}/FV/0{1 if first_december_number == 0 else 2}/2012")

    def test_duplicate_invoices(self):
        """
        Order.complete_order should not create duplicate invoice if called concurrently
        """
        biling_info = baker.make(BillingInfo)
        for i in range(20):  # Try this more times to increase chance of failure
            order = baker.make(Order, user=biling_info.user)
            Invoice.objects.all().delete()
            call_concurrently(3, complete_concrete_order, order_id=order.id)
            self.assertEqual(Invoice.objects.count(), 1)


class OrderTestCase(TestCase):
    fixtures = ['initial_plan', 'test_django-plans_auth', 'test_django-plans_plans']

    def test_order_complete_order(self):
        u = User.objects.get(username='test1')
        u.userplan.expire = date.today() + timedelta(days=50)
        u.userplan.active = False
        u.userplan.save()
        plan_pricing = PlanPricing.objects.get(plan=u.userplan.plan, pricing__period=30)
        order = Order.objects.create(
            user=u,
            pricing=plan_pricing.pricing,
            amount=100,
            plan=plan_pricing.plan,
        )
        self.assertTrue(order.complete_order())
        self.assertEqual(u.userplan.expire,
                         date.today() + timedelta(days=50) + timedelta(days=plan_pricing.pricing.period))
        self.assertEqual(u.userplan.plan, plan_pricing.plan)
        self.assertEqual(u.userplan.active, True)
        self.assertEqual(order.status, 2)  # completed
        self.assertEqual(order.plan_extended_from, date.today() + timedelta(days=50))
        self.assertEqual(order.plan_extended_until, date.today() + timedelta(days=50) +
                         timedelta(days=plan_pricing.pricing.period))
        self.assertEqual(len(mail.outbox), 3)

    def test_order_complete_order_invalid(self):
        u = User.objects.get(username='test1')
        u.userplan.expire = date.today() + timedelta(days=5)
        u.userplan.active = False
        u.userplan.save()
        plan_pricing = PlanPricing.objects.get(plan=u.userplan.plan, pricing__period=30)
        order = Order.objects.create(
            user=u,
            pricing=plan_pricing.pricing,
            amount=100,
            plan=PlanPricing.objects.all()[0].plan,
        )
        self.assertTrue(order.complete_order())
        self.assertEqual(u.userplan.expire,
                         date.today() + timedelta(days=5))
        self.assertEqual(u.userplan.plan, plan_pricing.plan)
        self.assertEqual(u.userplan.active, False)
        self.assertEqual(order.status, 3)  # not valid

    def test_order_complete_order_completed(self):
        """ Completed order doesn't get completed any more """
        u = User.objects.get(username='test1')
        u.userplan.expire = date.today() + timedelta(days=50)
        u.userplan.active = False
        u.userplan.save()
        plan_pricing = PlanPricing.objects.get(plan=u.userplan.plan, pricing__period=30)
        order = Order.objects.create(
            user=u,
            pricing=plan_pricing.pricing,
            amount=100,
            plan=plan_pricing.plan,
            completed=date(2010, 10, 10),
        )
        self.assertFalse(order.complete_order())

    def test_amount_taxed_none(self):
        o = Order()
        o.amount = Decimal(123)
        o.tax = None
        self.assertEqual(o.total(), Decimal('123'))

    def test_amount_taxed_0(self):
        o = Order()
        o.amount = Decimal(123)
        o.tax = Decimal(0)
        self.assertEqual(o.total(), Decimal('123'))

    def test_amount_taxed_23(self):
        o = Order()
        o.amount = Decimal(123)
        o.tax = Decimal(23)
        self.assertEqual(o.total(), Decimal('151.29'))


class PlanChangePolicyTestCase(TestCase):
    fixtures = ['initial_plan', 'test_django-plans_auth', 'test_django-plans_plans']

    def setUp(self):
        self.policy = PlanChangePolicy()

    def test_calculate_day_cost(self):
        plan = Plan.objects.get(pk=5)
        self.assertEqual(self.policy._calculate_day_cost(plan, 13), Decimal('6.67'))

    def test_get_change_price(self):
        p1 = Plan.objects.get(pk=3)
        p2 = Plan.objects.get(pk=4)
        self.assertEqual(self.policy.get_change_price(p1, p2, 23), Decimal('7.82'))
        self.assertEqual(self.policy.get_change_price(p2, p1, 23), None)

    def test_get_change_price1(self):
        p1 = Plan.objects.get(pk=3)
        p2 = Plan.objects.get(pk=4)
        self.assertEqual(self.policy.get_change_price(p1, p2, 53), Decimal('18.02'))
        self.assertEqual(self.policy.get_change_price(p2, p1, 53), None)

    def test_get_change_price2(self):
        p1 = Plan.objects.get(pk=3)
        p2 = Plan.objects.get(pk=4)
        self.assertEqual(self.policy.get_change_price(p1, p2, -53), None)
        self.assertEqual(self.policy.get_change_price(p1, p2, 0), None)


class StandardPlanChangePolicyTestCase(TestCase):
    fixtures = ['initial_plan', 'test_django-plans_auth', 'test_django-plans_plans']

    def setUp(self):
        self.policy = StandardPlanChangePolicy()

    def test_get_change_price(self):
        p1 = Plan.objects.get(pk=3)
        p2 = Plan.objects.get(pk=4)
        self.assertEqual(self.policy.get_change_price(p1, p2, 23), Decimal('8.60'))
        self.assertEqual(self.policy.get_change_price(p2, p1, 23), None)


class EUTaxationPolicyTestCase(TestCase):
    def setUp(self):
        self.policy = EUTaxationPolicy()

    def test_none(self):
        with self.settings(PLANS_TAX=Decimal('23.0'), PLANS_TAX_COUNTRY='PL'):
            self.assertEqual(self.policy.get_tax_rate(None, None), (Decimal('23.0'), True))

    def test_private_nonEU(self):
        with self.settings(PLANS_TAX=Decimal('23.0'), PLANS_TAX_COUNTRY='PL'):
            self.assertEqual(self.policy.get_tax_rate(None, 'RU'), (None, True))

    def test_private_EU_same(self):
        with self.settings(PLANS_TAX=Decimal('23.0'), PLANS_TAX_COUNTRY='PL'):
            self.assertEqual(self.policy.get_tax_rate(None, 'PL'), (Decimal('23.0'), True))

    def test_private_EU_notsame(self):
        with self.settings(PLANS_TAX=Decimal('23.0'), PLANS_TAX_COUNTRY='PL'):
            self.assertEqual(self.policy.get_tax_rate(None, 'AT'), (Decimal('20.0'), True))

    def test_company_nonEU(self):
        with self.settings(PLANS_TAX=Decimal('23.0'), PLANS_TAX_COUNTRY='PL'):
            self.assertEqual(self.policy.get_tax_rate('123456', 'RU'), (None, True))

    def test_company_EU_same(self):
        with self.settings(PLANS_TAX=Decimal('23.0'), PLANS_TAX_COUNTRY='PL'):
            self.assertEqual(self.policy.get_tax_rate('123456', 'PL'), (Decimal('23.0'), True))

    def test_company_EU_GR_vies_tax(self):
        """
        Test, that greece has VAT OK. Greece has code GR in django-countries, but EL in VIES
        Tax ID is not valid VAT ID, so tax is counted
        """
        self.assertEqual(self.policy.get_tax_rate('123456', 'GR'), (24, False))

    @mock.patch("stdnum.eu.vat.check_vies")
    def test_company_EU_GR_vies_zero(self, mock_check):
        """
        Test, that greece has VAT OK. Greece has code GR in django-countries, but EL in VIES
        Tax ID is valid VAT ID, so no tax is counted
        """
        mock_check.return_value = {'valid': True}
        self.assertEqual(self.policy.get_tax_rate('EL090145420', 'GR'), (None, True))

    @mock.patch("stdnum.eu.vat.check_vies")
    def test_company_EU_notsame_vies_ok(self, mock_check):
        mock_check.return_value = {'valid': True}
        with self.settings(PLANS_TAX=Decimal('23.0'), PLANS_TAX_COUNTRY='PL'):
            self.assertEqual(self.policy.get_tax_rate('123456', 'AT'), (None, True))

    @mock.patch("stdnum.eu.vat.check_vies")
    def test_company_EU_notsame_vies_not_ok(self, mock_check):
        mock_check.return_value = {'valid': False}
        with self.settings(PLANS_TAX=Decimal('23.0'), PLANS_TAX_COUNTRY='PL'):
            self.assertEqual(self.policy.get_tax_rate('123456', 'AT'), (Decimal('20.0'), True))


class BillingInfoTestCase(TestCase):
    def test_clean_tax_number(self):
        with self.assertRaises(ValidationError):
            BillingInfo.clean_tax_number('123456', 'CZ')

    def test_clean_tax_number_valid(self):
        self.assertEqual(BillingInfo.clean_tax_number('48136450', 'CZ'), 'CZ48136450')

    def test_clean_tax_number_valid_space(self):
        self.assertEqual(BillingInfo.clean_tax_number('48 136 450', 'CZ'), 'CZ48136450')

    def test_clean_tax_number_valid_with_country(self):
        self.assertEqual(BillingInfo.clean_tax_number('CZ48136450', 'CZ'), 'CZ48136450')

    def test_clean_tax_number_valid_with_country_GR(self):
        self.assertEqual(BillingInfo.clean_tax_number('GR104594676', 'GR'), 'EL104594676')

    def test_clean_tax_number_valid_with_country_EL(self):
        self.assertEqual(BillingInfo.clean_tax_number('EL104594676', 'GR'), 'EL104594676')

    def test_clean_tax_number_vat_id_is_not_correct(self):
        with self.assertRaisesRegex(ValidationError, 'VAT ID is not correct'):
            BillingInfo.clean_tax_number('GR48136450', 'GR')

    def test_clean_tax_number_country_code_does_not_equal_as_country(self):
        with self.assertRaisesRegex(ValidationError, 'VAT ID country code doesn\'t corespond with country'):
            BillingInfo.clean_tax_number('AT48136450', 'CZ')


def timeout(*args, **kwargs):
    raise requests.Timeout


class CreateOrderViewTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        request = self.factory.get('')
        middleware = SessionMiddleware(lambda x: x)
        middleware.process_request(request)
        messages = FallbackStorage(request)
        setattr(request, '_messages', messages)
        self.create_view = CreateOrderView()
        self.create_view.request = request

    def test_recalculate_order_no_connection(self):
        # VAT is right, but with no internet connection
        with no_connection():
            with patch('plans.taxation.eu.logger') as mock_logger:
                o = self.create_view.recalculate(10, BillingInfo(tax_number='48136450', country='CZ'))
                self.assertEqual(o.tax, 21)
                mock_logger.exception.assert_called_with("TAX_ID=CZ48136450")
        message = self.create_view.request._messages._queued_messages[0].message
        self.assertEqual(
            message,
            'There was an error during determining validity of your VAT ID.<br/>'
            'If you think, you have european VAT ID and should not be taxed, '
            'please try resaving billing info later.<br/><br/>'
            'European VAT Information Exchange System throw following error: '
            '&lt;urlopen error Internet is disabled&gt;',
        )

    @mock.patch("stdnum.eu.vat.check_vies")
    def test_recalculate_order(self, mock_check):
        mock_check.return_value = {'valid': True}
        # BE 0203.201.340 is VAT ID of Belgium national bank.
        # It is used, because national provider for VIES seems to be stable enough
        c = self.create_view
        o = c.recalculate(10, BillingInfo(tax_number='BE 0203 201 340', country='BE'))
        self.assertEqual(o.tax, None)

        o = c.recalculate(10, BillingInfo(tax_number='0203 201 340', country='BE'))
        self.assertEqual(o.tax, None)

        mock_check.return_value = {'valid': False}
        o = c.recalculate(10, BillingInfo(tax_number='1234565', country='BE'))
        self.assertEqual(o.tax, 21)

        o = c.recalculate(10, BillingInfo(tax_number='1234567', country='GR'))
        self.assertEqual(o.tax, 24)

        mock_check.return_value = {'valid': True}
        o = c.recalculate(10, BillingInfo(tax_number='090145420', country='GR'))
        self.assertEqual(o.tax, None)


class ValidatorsTestCase(TestCase):
    fixtures = ['test_django-plans_auth']

    def test_model_count_validator(self):
        """
        We create a test model validator for User. It will raise ValidationError when QUOTA_NAME value
        will be lower than number of elements of model User.
        """

        class TestValidator(ModelCountValidator):
            code = 'QUOTA_NAME'
            model = User

        validator_object = TestValidator()
        self.assertRaises(ValidationError, validator_object, user=None, quota_dict={'QUOTA_NAME': 1})
        self.assertEqual(validator_object(user=None, quota_dict={'QUOTA_NAME': 2}), None)
        self.assertEqual(validator_object(user=None, quota_dict={'QUOTA_NAME': 3}), None)

        #   TODO: FIX this test not to use Pricing for testing  ModelAttributeValidator
        # def test_model_attribute_validator(self):
        #     """
        #     We create a test attribute validator which will validate if Pricing objects has a specific value set.
        #     """
        #
        #     class TestValidator(ModelAttributeValidator):
        #         code = 'QUOTA_NAME'
        #         attribute = 'period'
        #         model = Pricing
        #
        #     validator_object = TestValidator()
        #     self.assertRaises(ValidationError, validator_object, user=None, quota_dict={'QUOTA_NAME': 360})
        #     self.assertEqual(validator_object(user=None, quota_dict={'QUOTA_NAME': 365}), None)


class BillingInfoViewTestCase(TestCase):
    fixtures = ['test_django-plans_auth']

    def setUp(self):
        self.user = User.objects.create_user('foo', 'myemail@test.com', 'bar')
        self.client.login(username='foo', password='bar')

    @override_settings(
        PLANS_GET_COUNTRY_FROM_IP=True,
        PLANS_DEFAULT_COUNTRY='PL',
    )
    def test_default_country_set(self):
        """
        Test, that default country is PL
        """
        response = self.client.get(reverse('billing_info'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<option value="PL" selected>Poland</option>', html=True)

    @override_settings(
        PLANS_DEFAULT_COUNTRY='PL',
    )
    def test_default_country_set_no_ip(self):
        """
        Test, that default country is PL
        """
        response = self.client.get(reverse('billing_info'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<option value="PL" selected>Poland</option>', html=True)

    @override_settings(PLANS_GET_COUNTRY_FROM_IP=True)
    def test_default_country_unset(self):
        """
        Test, that default country is None
        """
        response = self.client.get(reverse('billing_info'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<option value="" selected>---------</option>', html=True)

    @override_settings(PLANS_GET_COUNTRY_FROM_IP=True)
    def test_default_country_by_ip(self):
        """
        Test, that default country is determined by German IP
        """

        response = self.client.get(reverse('billing_info'), HTTP_X_FORWARDED_FOR='85.214.132.117')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<option value="DE" selected>Germany</option>', html=True)

        response = self.client.get(reverse('billing_info'), REMOTE_ADDR='85.214.132.117')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<option value="DE" selected>Germany</option>', html=True)

    def test_default_country_by_ip_no_settings(self):
        """
        Test, that default country is not determined
        """

        response = self.client.get(reverse('billing_info'), HTTP_X_FORWARDED_FOR='85.214.132.117')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<option value="" selected>---------</option>', html=True)

    def test_billing_info(self):
        """
        Test, BillingInfoCreateOrUpdateView and BillingInfoDeleteView views
        """
        # Test get does not contain delete button
        response = self.client.get(reverse('billing_info'))
        self.assertNotContains(response, '<a class="btn btn-danger" href="/plan/billing/delete/">Delete</a>', html=True)

        # Test create
        parameters = {
            "country": "GR",
            "tax_number": "GR104594676",
            "name": "bar",
            "street": "baz",
            "city": "bay",
            "zipcode": "bax",
        }
        response = self.client.post(reverse('billing_info') + "?next=/plan/pricing/", parameters)
        self.assertRedirects(
            response, '/plan/pricing/', status_code=302,
            target_status_code=200, fetch_redirect_response=True,
        )
        self.assertEqual(self.user.billinginfo.tax_number, "EL104594676")

        # Test get contains delete button
        response = self.client.get(reverse('billing_info'))
        self.assertContains(response, '<a class="btn btn-danger" href="/plan/billing/delete/">Delete</a>', html=True)

        # Test update
        del parameters["tax_number"]
        parameters["name"] = "foo"
        response = self.client.post(reverse('billing_info') + "?next=/plan/pricing/", parameters)
        self.user.billinginfo.refresh_from_db()
        self.assertEqual(self.user.billinginfo.name, "foo")
        self.assertEqual(self.user.billinginfo.tax_number, "")

        # Test delete
        response = self.client.post(reverse('billing_info_delete'))
        with self.assertRaises(BillingInfo.DoesNotExist):
            self.user.billinginfo.refresh_from_db()


class RecurringPlansTestCase(TestCase):

    def test_set_plan_renewal(self):
        """ Test that UserPlan.set_plan_renewal() method """
        up = baker.make('UserPlan')
        o = baker.make('Order', amount=10)
        up.set_plan_renewal(order=o, card_masked_number="1234")
        self.assertEqual(up.recurring.amount, 10)
        self.assertEqual(up.recurring.card_masked_number, "1234")

        # test setting new values
        up.set_plan_renewal(order=o)
        self.assertEqual(up.recurring.amount, 10)
        self.assertEqual(up.recurring.card_masked_number, None)

    def test_plan_autorenew_at(self):
        """ Test that UserPlan.plan_autorenew_at() method """
        up = baker.make('UserPlan')
        self.assertEqual(up.plan_autorenew_at(), None)

    def test_plan_autorenew_at_expire(self):
        """ Test that UserPlan.plan_autorenew_at() method """
        up = baker.make('UserPlan', expire=date(2020, 1, 1))
        self.assertEqual(up.plan_autorenew_at(), date(2020, 1, 1))

    @override_settings(
        PLANS_AUTORENEW_BEFORE_DAYS=3,
        PLANS_AUTORENEW_BEFORE_HOURS=24,
    )
    def test_plan_autorenew_at_settings(self):
        """ Test that UserPlan.plan_autorenew_at() method """
        up = baker.make('UserPlan', expire=date(2020, 1, 5))
        self.assertEqual(up.plan_autorenew_at(), date(2020, 1, 1))

    def test_has_automatic_renewal(self):
        """ Test UserPlan.has_automatic_renewal() method """
        user_plan = baker.make('UserPlan')
        order = baker.make('Order', amount=10)
        user_plan.set_plan_renewal(order=order, card_masked_number="1234")
        self.assertEqual(user_plan.has_automatic_renewal(), False)

        user_plan.recurring.token_verified = True
        self.assertEqual(user_plan.has_automatic_renewal(), True)

    def test_create_new_order(self):
        rup = baker.make(
            'RecurringUserPlan',
            user_plan__user__billinginfo__country='CZ',
            amount=10,
        )
        order = rup.create_renew_order()
        self.assertEqual(order.tax, 21)
        self.assertEqual(rup.tax, 21)

    def test_create_new_order_VIES_fault(self):
        """ If VIES fails, we use last available TAX value """
        rup = baker.make(
            'RecurringUserPlan',
            user_plan__user__billinginfo__country='CZ',
            user_plan__user__billinginfo__tax_number="CZ0123",
            amount=10,
            tax=11,
        )
        with no_connection():
            order = rup.create_renew_order()
        self.assertEqual(order.tax, 11)


class TasksTestCase(TestCase):
    def test_expire_account_task(self):
        order = baker.make('Order', amount=10)
        userplan = baker.make('UserPlan', user=baker.make('User'))
        userplan.expire = date.today() - timedelta(days=1)
        userplan.active = True

        # If the automatic renewal didn't go through, even automatic renewal plans has to go
        userplan.set_plan_renewal(order=order, card_masked_number="1234")

        userplan.save()
        tasks.expire_account()

        userplan.refresh_from_db()
        self.assertEqual(userplan.active, False)
        # self.assertEqual(len(mail.outbox), 1)
