from decimal import Decimal
from datetime import date
from datetime import timedelta
from io import StringIO

from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.conf import settings
from django.core import mail
from django.core.management import call_command
from django.db.models import Q
from django.utils import six


if six.PY2:
    import mock
elif six.PY3:
    from unittest import mock

from plans.models import PlanPricing, Invoice, Order, Plan, PlanQuota, UserPlan
from plans.plan_change import PlanChangePolicy, StandardPlanChangePolicy
from plans.taxation.eu import EUTaxationPolicy
from plans.quota import get_user_quota
from plans.validators import ModelCountValidator


User = get_user_model()


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
        Tests extending account with other Plan that user had before:
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
        settings.PLANS_INVOICE_NUMBER_FORMAT = "{{ invoice.number }}/{% ifequal " \
                                         "invoice.type invoice.INVOICE_TYPES.PROFORMA %}PF{% else %}FV" \
                                         "{% endifequal %}/{{ invoice.issued|date:'m/Y' }}"
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
        settings.PLANS_INVOICE_NUMBER_FORMAT = "{{ invoice.number }}/{% ifequal " \
                                         "invoice.type invoice.INVOICE_TYPES.PROFORMA %}PF{% else %}FV" \
                                         "{% endifequal %}/{{ invoice.issued|date:'d/m/Y' }}"
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
        settings.PLANS_INVOICE_NUMBER_FORMAT = "{{ invoice.number }}/{% ifequal " \
                                         "invoice.type invoice.INVOICE_TYPES.PROFORMA %}PF{% else %}FV" \
                                         "{% endifequal %}/{{ invoice.issued|date:'m/Y' }}"
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
        settings.PLANS_INVOICE_NUMBER_FORMAT = "{{ invoice.number }}/{% ifequal " \
                                         "invoice.type invoice.INVOICE_TYPES.PROFORMA %}PF{% else %}FV" \
                                         "{% endifequal %}/{{ invoice.issued|date:'Y' }}"
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


class OrderTestCase(TestCase):
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
            self.assertEqual(self.policy.get_tax_rate(None, None), Decimal('23.0'))

    def test_private_nonEU(self):
        with self.settings(PLANS_TAX=Decimal('23.0'), PLANS_TAX_COUNTRY='PL'):
            self.assertEqual(self.policy.get_tax_rate(None, 'RU'), None)

    def test_private_EU_same(self):
        with self.settings(PLANS_TAX=Decimal('23.0'), PLANS_TAX_COUNTRY='PL'):
            self.assertEqual(self.policy.get_tax_rate(None, 'PL'), Decimal('23.0'))

    def test_private_EU_notsame(self):
        with self.settings(PLANS_TAX=Decimal('23.0'), PLANS_TAX_COUNTRY='PL'):
            self.assertEqual(self.policy.get_tax_rate(None, 'AT'), Decimal('20.0'))

    def test_company_nonEU(self):
        with self.settings(PLANS_TAX=Decimal('23.0'), PLANS_TAX_COUNTRY='PL'):
            self.assertEqual(self.policy.get_tax_rate('123456', 'RU'), None)

    def test_company_EU_same(self):
        with self.settings(PLANS_TAX=Decimal('23.0'), PLANS_TAX_COUNTRY='PL'):
            self.assertEqual(self.policy.get_tax_rate('123456', 'PL'), Decimal('23.0'))

    @mock.patch("vatnumber.check_vies", lambda x: True)
    def test_company_EU_notsame_vies_ok(self):
        with self.settings(PLANS_TAX=Decimal('23.0'), PLANS_TAX_COUNTRY='PL'):
            self.assertEqual(self.policy.get_tax_rate('123456', 'AT'), None)

    @mock.patch("vatnumber.check_vies", lambda x: False)
    def test_company_EU_notsame_vies_not_ok(self):
        with self.settings(PLANS_TAX=Decimal('23.0'), PLANS_TAX_COUNTRY='PL'):
            self.assertEqual(self.policy.get_tax_rate('123456', 'AT'), Decimal('20.0'))


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
