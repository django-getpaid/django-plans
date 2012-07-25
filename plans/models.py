from collections import defaultdict
from decimal import Decimal
import re
from django.core.urlresolvers import reverse
from django.template.base import Template
from django.utils.translation import ugettext_lazy as _
from django.db import models
from ordered_model.models import OrderedModel
import vatnumber
from model_fields import CountryField
from django.core import mail
from django.template import loader, Context
from django.conf import settings
from datetime import date, timedelta
from django.core.exceptions import ImproperlyConfigured, ValidationError
from transmeta import TransMeta
import logging
from mydjango.enum import Enumeration

accounts_logger = logging.getLogger('accounts')

# Create your models here.

class Plan(OrderedModel):


    name = models.CharField(_('name'), max_length=100)
    description = models.TextField(_('description'), blank=True)
    available = models.BooleanField(_('available'), default=False, db_index=True)
    created = models.DateTimeField(_('created'), auto_now_add=True, db_index=True)
    customized = models.ForeignKey('auth.User', null=True, blank=True, verbose_name=_('customized'))
    quotas = models.ManyToManyField('Quota', through='PlanQuota', verbose_name=_('quotas'))

    __metaclass__ = TransMeta
    class Meta:
        translate = ('name', 'description', )
        ordering = ('order',)

    def __unicode__(self):
        if self.available:
            return "* %s" % (self.name)
        else:
            return "%s" % (self.name)


class BillingInfo(models.Model):
    """
    Stores customer billing data needed to issue an invoice
    """
    user = models.OneToOneField('auth.User', verbose_name=_('user'))
    name = models.CharField(_('name'), max_length=200, )
    street = models.CharField(_('street'), max_length=200)
    zipcode = models.CharField(_('zip code'), max_length=200)
    city = models.CharField(_('city'), max_length=200)
    country = CountryField(_("country"), default='PL')
    tax_number = models.CharField(_('VAT ID'), max_length=200, blank=True)

    @staticmethod
    def clean_tax_number(tax_number, country):
        tax_number = re.sub(r'[^A-Z0-9]', '',  tax_number.upper())
        if tax_number:

            if country in vatnumber.countries():
                number = tax_number
                if tax_number.startswith(country):
                    number = tax_number[len(country):]

                if not vatnumber.check_vat(country + number):

#           This is a proper solution to bind ValidationError to a Field but it is not
#           working due to django bug :(
#                    errors = defaultdict(list)
#                    errors['tax_number'].append(_('VAT ID is not correct'))
#                    raise ValidationError(errors)
                    raise ValidationError(_('VAT ID is not correct'))

            return tax_number
        else:
            return ''

# FIXME: How to make validation in Model clean and attach it to a field? Seems that it is not working right now
#    def clean(self):
#        super(BillingInfo, self).clean()
#        self.tax_number = BillingInfo.clean_tax_number(self.tax_number, self.country)

class UserPlan(models.Model):
    user = models.OneToOneField('auth.User', verbose_name=_('user'))
    plan = models.ForeignKey('Plan', verbose_name=_('plan'))
    expire = models.DateField(_('expire'), db_index=True)
    active = models.BooleanField(_('active'), default=True, db_index=True)

    def __unicode__(self):
        return "%s [%s]" % (self.user, self.plan)

    def quotas(self):
        quotas = {}
        for quota in self.plan.planquota_set.all():
            quotas[quota]

    def extend_account(self, plan_pricing):
        self.active = True
        if self.plan == plan_pricing.plan:
            if self.expire > date.today():
                self.expire += timedelta(days=plan_pricing.pricing.period)
            else:
                self.expire = date.today() + timedelta(days=plan_pricing.pricing.period)
        else:
            self.plan = plan_pricing.plan
            self.expire = date.today() + timedelta(days=plan_pricing.pricing.period)
        self.save()

        accounts_logger.info(u"Account '%s' [id=%d] has been extended by %d days using plan '%s' [id=%d]" % (
            self.user, self.user.pk, plan_pricing.pricing.period, plan_pricing.plan, plan_pricing.plan.pk))

        #TODO: dynamically change a language of e-mail depending on user language 

        mail_title_template = loader.get_template('mail/extend_account_title.txt')
        mail_body_template = loader.get_template('mail/extend_account_body.txt')
        mail_context = Context(
                {'user': self.user, 'userplan': self, 'plan_pricing': plan_pricing, 'plan': plan_pricing.plan,
                 'pricing': plan_pricing.pricing})

        try:
            email_from = getattr(settings, 'DEFAULT_FROM_EMAIL')
        except AttributeError:
            raise ImproperlyConfigured('DEFAULT_FROM_EMAIL setting needed for sending e-mails')

        mail.send_mail(mail_title_template.render(mail_context), mail_body_template.render(mail_context), email_from,
            [self.user.email])

    def expire_account(self):
        """manages account expiration"""
        self.active = False
        self.save()
        accounts_logger.info(u"Account '%s' [id=%d] has expired" % (self.user, self.user.pk))
        #TODO: dynamically change a language of e-mail depending on user language 
        mail_title_template = loader.get_template('mail/expired_account_title.txt')
        mail_body_template = loader.get_template('mail/expired_account_body.txt')
        mail_context = Context({'user': self.user, 'userplan': self})

        try:
            email_from = getattr(settings, 'DEFAULT_FROM_EMAIL')
        except AttributeError:
            raise ImproperlyConfigured('DEFAULT_FROM_EMAIL setting needed for sending e-mails')

        mail.send_mail(mail_title_template.render(mail_context), mail_body_template.render(mail_context), email_from,
            [self.user.email])

    def remind_expire_soon(self):
        """reminds about soon account expiration"""
        accounts_logger.info(u"Expire reminder for an account '%s' [id=%d] has been sent - %d days left." % (
            self.user, self.user.pk, (self.expire - date.today()).days))
        #TODO: dynamically change a language of e-mail depending on user language 
        mail_title_template = loader.get_template('mail/remind_expire_title.txt')
        mail_body_template = loader.get_template('mail/remind_expire_body.txt')
        mail_context = Context({'user': self.user, 'userplan': self, 'days': (self.expire - date.today()).days})

        try:
            email_from = getattr(settings, 'DEFAULT_FROM_EMAIL')
        except AttributeError:
            raise ImproperlyConfigured('DEFAULT_FROM_EMAIL setting needed for sending e-mails')

        mail.send_mail(mail_title_template.render(mail_context), mail_body_template.render(mail_context), email_from,
            [self.user.email])


class Pricing(models.Model):
    name = models.CharField(_('name'), max_length=100)
    period = models.PositiveIntegerField(_('period'), default=30, null=True, blank=True, db_index=True)

    __metaclass__ = TransMeta

    class Meta:
        translate = ('name', )
        ordering = ('period',)

    def __unicode__(self):
        return u"%s (%d "  % (self.name, self.period) + unicode(_("days")) + u")"




class Quota(OrderedModel):
    codename = models.CharField(_('codename'), max_length=50, unique=True, db_index=True)
    name = models.CharField(_('name'), max_length=100)
    unit = models.CharField(_('unit'), max_length=100, blank=True)
    description = models.TextField(_('description'), blank=True)
    is_boolean = models.BooleanField(_('is boolean'), default=False)

    __metaclass__ = TransMeta

    class Meta:
        translate = ('name', 'description', 'unit')
        ordering = ('order',)

    def __unicode__(self):
        return "%s" % (self.codename, )


class PlanPricingManager(models.Manager):
    def get_query_set(self):
        return super(PlanPricingManager, self).get_query_set().select_related('plan', 'pricing')


class PlanPricing(models.Model):
    plan = models.ForeignKey('Plan')
    pricing = models.ForeignKey('Pricing')
    price = models.DecimalField(max_digits=7, decimal_places=2, db_index=True)

    objects = PlanPricingManager()

    def __unicode__(self):
        return "%s %s" % (self.plan.name, self.pricing)

class PlanQuotaManager(models.Manager):
    def get_query_set(self):
        return super(PlanQuotaManager, self).get_query_set().select_related('plan', 'quota')


class PlanQuota(models.Model):
    plan = models.ForeignKey('Plan')
    quota = models.ForeignKey('Quota')
    value = models.IntegerField(default=1, null=True, blank=True)

    objects = PlanQuotaManager()


class Order(models.Model):
    user = models.ForeignKey('auth.User', verbose_name=_('user'))
#    pricing = models.ForeignKey('PlanPricing', verbose_name=_('plan pricing'))
    plan = models.ForeignKey('Plan', verbose_name=_('plan'), related_name="plan_order")
    pricing = models.ForeignKey('Pricing', verbose_name=_('pricing'))
    created = models.DateTimeField(_('created'), auto_now_add=True, db_index=True)
    completed = models.DateTimeField(_('completed'), null=True, blank=True, db_index=True)
    amount = models.DecimalField(_('amount'), max_digits=7, decimal_places=2, db_index=True)
    tax = models.DecimalField(_('tax'), max_digits=4, decimal_places=2, db_index=True, null=True,
        blank=True) # Tax=None is when tax is not applicable
    currency = models.CharField(_('currency'), max_length=3, default='EUR')


    def get_invoices_proforma(self):
        return Invoice.proforma.filter(order=self)

    def get_invoices(self):
        return Invoice.invoices.filter(order=self)

    def total(self):
        if self.tax is not None:
            return (self.amount * (self.tax + 100) / 100).quantize(Decimal('1.00'))
        else:
            return self.amount


    def get_absolute_url(self):
        return reverse('order', kwargs={'pk':self.pk})

    class Meta:
        ordering = ('-created', )


class InvoiceManager(models.Manager):
    def get_query_set(self):
        return super(InvoiceManager, self).get_query_set().filter(type=Invoice.INVOICE_TYPES['INVOICE'])


class InvoiceProformaManager(models.Manager):
    def get_query_set(self):
        return super(InvoiceProformaManager, self).get_query_set().filter(type=Invoice.INVOICE_TYPES['PROFORMA'])

class InvoiceDuplicateManager(models.Manager):
    def get_query_set(self):
        return super(InvoiceDuplicateManager, self).get_query_set().filter(type=Invoice.INVOICE_TYPES['DUPLICATE'])


class Invoice(models.Model):
    """
    Single invoice document.
    """
    INVOICE_TYPES = Enumeration([(1, 'INVOICE', _('Invoice')),
        (2, 'DUPLICATE', _('Invoice Duplicate')),
        (3, 'PROFORMA', _('Pro Forma Invoice')),

    ])

    objects = models.Manager()
    invoices = InvoiceManager()
    proforma = InvoiceProformaManager()
    duplicates = InvoiceDuplicateManager()


    class NUMBERING:
        """
        Used as a choices for settings.INVOICE_COUNTER_RESET
        """
        DAILY = 1
        MONTHLY = 2
        ANNUALLY = 3


    user = models.ForeignKey('auth.User')
    order = models.ForeignKey('Order')

    number = models.IntegerField(db_index=True)
    full_number = models.CharField(max_length=200, editable=False)

    type = models.IntegerField(choices=INVOICE_TYPES, default=INVOICE_TYPES.INVOICE, editable=False, db_index=True)

    issued = models.DateField(db_index=True)
    issued_duplicate = models.DateField(db_index=True, null=True, blank=True)

    selling_date = models.DateField()
    payment_date = models.DateField()

    unit_price_net = models.DecimalField(max_digits=7, decimal_places=2)

    quantity = models.IntegerField(default=1)

    total_net = models.DecimalField(max_digits=7, decimal_places=2)
    total = models.DecimalField(max_digits=7, decimal_places=2)
    tax_total = models.DecimalField(max_digits=7, decimal_places=2)

    tax = models.DecimalField(max_digits=4, decimal_places=2, db_index=True, null=True,
        blank=True) # Tax=None is whet tax is not applicable
    rebate = models.DecimalField(max_digits=4, decimal_places=2, default=Decimal(0))
    currency = models.CharField(max_length=3, default='EUR')
    item_description = models.CharField(max_length=200)

    buyer_name = models.CharField(max_length=200, verbose_name=_("Name"))
    buyer_street = models.CharField(max_length=200, verbose_name=_("Street"))
    buyer_zipcode = models.CharField(max_length=200, verbose_name=_("Zip code"))
    buyer_city = models.CharField(max_length=200, verbose_name=_("City"))
    buyer_country = CountryField(verbose_name=_("Country"), default='PL')
    buyer_tax_number = models.CharField(max_length=200, blank=True, verbose_name=_("TAX/VAT number"))

    shipping_name = models.CharField(max_length=200, verbose_name=_("Name"))
    shipping_street = models.CharField(max_length=200, verbose_name=_("Street"))
    shipping_zipcode = models.CharField(max_length=200, verbose_name=_("Zip code"))
    shipping_city = models.CharField(max_length=200, verbose_name=_("City"))
    shipping_country = CountryField(verbose_name=_("Country"), default='PL')

    require_shipment = models.BooleanField(default=False, db_index=True)

    issuer_name = models.CharField(max_length=200, verbose_name=_("Name"))
    issuer_street = models.CharField(max_length=200, verbose_name=_("Street"))
    issuer_zipcode = models.CharField(max_length=200, verbose_name=_("Zip code"))
    issuer_city = models.CharField(max_length=200, verbose_name=_("City"))
    issuer_country = CountryField(verbose_name=_("Country"), default='PL')
    issuer_tax_number = models.CharField(max_length=200, blank=True, verbose_name=_("TAX/VAT number"))

    #    def save(self, force_insert=False, force_update=False, using=None):
    #
    #        super(Invoice, self).save(force_insert, force_update, using)
    def __unicode__(self):
        return self.full_number

    def get_absolute_url(self):
        return reverse('invoice_preview_html', kwargs={'pk': self.pk})

    def clean(self):
        if self.number is None:
            invoice_counter_reset = getattr(settings, 'INVOICE_COUNTER_RESET', Invoice.NUMBERING.MONTHLY)

            if invoice_counter_reset == Invoice.NUMBERING.DAILY:
                count = Invoice.objects.filter(issued=self.issued).count()
            elif invoice_counter_reset == Invoice.NUMBERING.MONTHLY:
                count = Invoice.objects.filter(issued__year=self.issued.year, issued__month=self.issued.month).count()
            elif invoice_counter_reset == Invoice.NUMBERING.ANNUALLY:
                count = Invoice.objects.filter(issued__year=self.issued.year).count()
            else:
                raise ImproperlyConfigured("INVOICE_COUNTER_RESET can be set only to these values: daily, monthly, yearly.")
            self.number = 1 if count == 0 else count + 1


        if self.full_number is "":
            self.full_number = self.get_full_number()
        super(Invoice, self).clean()

#    def validate_unique(self, exclude=None):
#        super(Invoice, self).validate_unique(exclude)
#        if self.type == Invoice.INVOICE_TYPES.INVOICE:
#            if Invoice.objects.filter(order=self.order).count():
#                raise ValidationError("Duplicate invoice for order")
#        if self.type in (Invoice.INVOICE_TYPES.INVOICE, Invoice.INVOICE_TYPES.PROFORMA):
#            pass


    def get_full_number(self):
        """
        Generates on the fly invoice full number from template provided by ``settings.INVOICE_NUMBER_FORMAT``.
        ``Invoice`` object is provided as ``invoice`` variable to the template, therefore all object fields
        can be used to generate full number format.

        .. warning::

            This is only used to prepopulate ``full_number`` field on saving new invoice.
            To get invoice full number always use ``full_number`` field.

        :return: string (generated full number)
        """
        format = getattr(settings, "INVOICE_NUMBER_FORMAT",
            "{{ invoice.number }}/{% ifequal invoice.type invoice.INVOICE_TYPES.PROFORMA %}PF{% else %}FV{% endifequal %}/{{ invoice.issued|date:'m/Y' }}")
        return Template(format).render(Context({'invoice': self}))


    def set_issuer_invoice_data(self):
        """
        Fills models object with issuer data copied from ``settings.ISSUER_DATA``

        :raise: ImproperlyConfigured
        """
        try:
            issuer = getattr(settings, 'ISSUER_DATA')
        except:
            raise ImproperlyConfigured("Please set ISSUER_DATA in order to make an invoice.")
        self.issuer_name = issuer['issuer_name']
        self.issuer_street = issuer['issuer_street']
        self.issuer_zipcode = issuer['issuer_zipcode']
        self.issuer_city = issuer['issuer_city']
        self.issuer_country = issuer['issuer_country']
        self.issuer_tax_number = issuer['issuer_tax_number']

    def set_buyer_invoice_data(self, billing_info):
        """
        Fill buyer invoice billing and shipping data by copy them from provided user's ``BillingInfo`` object.

        :param billing_info: BillingInfo object
        :type billing_info: BillingInfo
        """
        self.buyer_name = billing_info.name
        self.buyer_street = billing_info.street
        self.buyer_zipcode = billing_info.zipcode
        self.buyer_city = billing_info.city
        self.buyer_country = billing_info.country
        self.buyer_tax_number = billing_info.tax_number

        #TODO: different shipping data?
        self.shipping_name = billing_info.name
        self.shipping_street = billing_info.street
        self.shipping_zipcode = billing_info.zipcode
        self.shipping_city = billing_info.city
        self.shipping_country = billing_info.country

    def copy_from_order(self, order):
        """
        Filling orders details likes totals, taxes, etc and linking provided ``Order`` object with an invoice

        :param order: Order object
        :type order: Order
        """
        self.order = order
        self.user = order.user
        self.unit_price_net = order.amount
        self.total_net = order.amount
        self.total = order.total()
        self.tax_total = order.total() - order.amount
        self.tax = order.tax
        self.currency = order.currency
        self.item_description = unicode(_("Plan")) + u" %s (%s " % (order.plan.name, order.pricing.period)  + unicode(_("days")) + u")"


#noinspection PyUnresolvedReferences
import plans.listeners