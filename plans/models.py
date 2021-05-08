from __future__ import unicode_literals

import re
import logging
import vatnumber

from decimal import Decimal
from datetime import date, timedelta

from django.db import models, transaction

from django.conf import settings
from django.contrib.auth import get_user_model
try:
    from django.contrib.sites.models import Site
except RuntimeError:
    Site = None
from django.urls import reverse

from django.template import Context
from django.template.base import Template
from django.utils import translation
from django.utils.timezone import now
from django.utils.translation import ugettext_lazy as _, pgettext_lazy

from django_countries.fields import CountryField
from ordered_model.models import OrderedModel
from django.core.exceptions import ImproperlyConfigured, ValidationError

from plans.enumeration import Enumeration
from plans.validators import plan_validation
from plans.taxation.eu import EUTaxationPolicy
from plans.contrib import send_template_email, get_user_language
from plans.signals import (order_completed, account_activated,
                           account_expired, account_change_plan,
                           account_deactivated)

from sequences import get_next_value

accounts_logger = logging.getLogger('accounts')

# Create your models here.


class Plan(OrderedModel):
    """
    Single plan defined in the system. A plan can customized (referred to user) which means
    that only this user can purchase this plan and have it selected.

    Plan also can be visible and available. Plan is displayed on the list of currently available plans
    for user if it is visible. User cannot change plan to a plan that is not visible. Available means
    that user can buy a plan. If plan is not visible but still available it means that user which
    is using this plan already will be able to extend this plan again. If plan is not visible and not
    available, he will be forced then to change plan next time he extends an account.
    """
    name = models.CharField(_('name'), max_length=100)
    description = models.TextField(_('description'), blank=True)
    default = models.BooleanField(
        help_text=_('Both "Unknown" and "No" means that the plan is not default'),
        default=None,
        db_index=True,
        unique=True,
        null=True,
    )
    available = models.BooleanField(
        _('available'), default=False, db_index=True,
        help_text=_('Is still available for purchase')
    )
    visible = models.BooleanField(
        _('visible'), default=True, db_index=True,
        help_text=_('Is visible in current offer')
    )
    created = models.DateTimeField(_('created'), db_index=True)
    customized = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        verbose_name=_('customized'),
        on_delete=models.CASCADE
    )
    quotas = models.ManyToManyField('Quota', through='PlanQuota')
    url = models.URLField(max_length=200, blank=True, help_text=_(
        'Optional link to page with more information (for clickable pricing table headers)'))

    class Meta:
        ordering = ('order',)
        verbose_name = _("Plan")
        verbose_name_plural = _("Plans")

    def save(self, *args, **kwargs):
        if not self.created:
            self.created = now()

        super(Plan, self).save(*args, **kwargs)

    @classmethod
    def get_default_plan(cls):
        try:
            return_value = cls.objects.get(default=True)
        except cls.DoesNotExist:
            return_value = None
        return return_value

    @classmethod
    def get_current_plan(cls, user):
        """ Get current plan for user. If userplan is expired, get default plan """
        if not user or user.is_anonymous or not hasattr(user, 'userplan') or user.userplan.is_expired():
            default_plan = Plan.get_default_plan()
            if default_plan is None or not default_plan.is_free():
                raise ValidationError(_('User plan has expired'))
            return default_plan
        return user.userplan.plan

    def __str__(self):
        return self.name

    def get_quota_dict(self):
        quota_dic = {}
        for plan_quota in PlanQuota.objects.filter(plan=self).select_related('quota'):
            quota_dic[plan_quota.quota.codename] = plan_quota.value
        return quota_dic

    def is_free(self):
        return self.planpricing_set.count() == 0
    is_free.boolean = True


class BillingInfo(models.Model):
    """
    Stores customer billing data needed to issue an invoice
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, verbose_name=_('user'),
        on_delete=models.CASCADE
    )
    tax_number = models.CharField(
        _('VAT ID'), max_length=200, blank=True, db_index=True
    )
    name = models.CharField(_('name'), max_length=200, db_index=True)
    street = models.CharField(_('street'), max_length=200)
    zipcode = models.CharField(_('zip code'), max_length=200)
    city = models.CharField(_('city'), max_length=200)
    country = CountryField(_("country"))
    shipping_name = models.CharField(
        _('name (shipping)'), max_length=200, blank=True, help_text=_('optional'))
    shipping_street = models.CharField(
        _('street (shipping)'), max_length=200, blank=True, help_text=_('optional'))
    shipping_zipcode = models.CharField(
        _('zip code (shipping)'), max_length=200, blank=True, help_text=_('optional'))
    shipping_city = models.CharField(
        _('city (shipping)'), max_length=200, blank=True, help_text=_('optional'))

    class Meta:
        verbose_name = _("Billing info")
        verbose_name_plural = _("Billing infos")

    @staticmethod
    def clean_tax_number(tax_number, country):
        tax_number = re.sub(r'[^A-Z0-9]', '', tax_number.upper())
        if tax_number and country:

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
    """
    Currently selected plan for user account.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, verbose_name=_('user'),
        on_delete=models.CASCADE
    )
    plan = models.ForeignKey('Plan', verbose_name=_('plan'), on_delete=models.CASCADE)
    expire = models.DateField(
        _('expire'), default=None, blank=True, null=True, db_index=True)
    active = models.BooleanField(_('active'), default=True, db_index=True)

    class Meta:
        verbose_name = _("User plan")
        verbose_name_plural = _("Users plans")

    def __str__(self):
        return "%s [%s]" % (self.user, self.plan)

    def is_active(self):
        return self.active

    def is_expired(self):
        if self.expire is None:
            return False
        else:
            return self.expire < date.today()

    def days_left(self):
        if self.expire is None:
            return None
        else:
            return (self.expire - date.today()).days

    def clean_activation(self):
        errors = plan_validation(self.user)
        if not errors['required_to_activate']:
            plan_validation(self.user, on_activation=True)
            self.activate()
        else:
            self.deactivate()
        return errors

    def activate(self):
        if not self.active:
            self.active = True
            self.save()
            account_activated.send(sender=self, user=self.user)

    def deactivate(self):
        if self.active:
            self.active = False
            self.save()
            account_deactivated.send(sender=self, user=self.user)

    def initialize(self):
        """
        Set up user plan for first use
        """
        if not self.is_active():
            # Plans without pricings don't need to expire
            if self.expire is None and self.plan.planpricing_set.count():
                self.expire = now() + timedelta(
                    days=getattr(settings, 'PLANS_DEFAULT_GRACE_PERIOD', 30))
            self.activate()  # this will call self.save()

    def get_plan_extended_from(self, plan):
        if plan.is_free():
            return None
        if not self.is_expired() and self.expire is not None and self.plan == plan:
            return self.expire
        return date.today()

    def get_plan_extended_until(self, plan, pricing):
        if plan.is_free():
            return None
        if not self.plan.is_free() and self.expire is None:
            return None
        if pricing is None:
            return self.expire
        return self.get_plan_extended_from(plan) + timedelta(days=pricing.period)

    def plan_autorenew_at(self):
        """
        Helper function which calculates when the plan autorenewal will occur
        """
        if self.expire:
            plans_autorenew_before_days = getattr(settings, 'PLANS_AUTORENEW_BEFORE_DAYS', 0)
            plans_autorenew_before_hours = getattr(settings, 'PLANS_AUTORENEW_BEFORE_HOURS', 0)
            return self.expire - timedelta(days=plans_autorenew_before_days, hours=plans_autorenew_before_hours)

    def set_plan_renewal(self, order, has_automatic_renewal=True, **kwargs):
        """
        Creates or updates plan renewal information for this userplan with given order
        """
        if hasattr(self, 'recurring'):
            # Delete the plan to populate with default values
            # We don't want to mix the old and new values
            self.recurring.delete()
        recurring = RecurringUserPlan.objects.create(
            user_plan=self,
            pricing=order.pricing,
            amount=order.amount,
            tax=order.tax,
            currency=order.currency,
            has_automatic_renewal=has_automatic_renewal,
            **kwargs,
        )
        return recurring

    def extend_account(self, plan, pricing):
        """
        Manages extending account after plan or pricing order
        :param plan:
        :param pricing: if pricing is None then account will be only upgraded
        :return:
        """

        status = False  # flag; if extending account was successful?
        expire = self.get_plan_extended_until(plan, pricing)
        if pricing is None:
            # Process a plan change request (downgrade or upgrade)
            # No account activation or extending at this point
            self.plan = plan

            if self.expire is not None and not plan.planpricing_set.count():
                # Assume no expiry date for plans without pricing.
                self.expire = None

            self.save()
            account_change_plan.send(sender=self, user=self.user)
            if getattr(settings, 'PLANS_SEND_EMAILS_PLAN_CHANGED', True):
                mail_context = {'user': self.user, 'userplan': self, 'plan': plan}
                send_template_email([self.user.email], 'mail/change_plan_title.txt', 'mail/change_plan_body.txt',
                                    mail_context, get_user_language(self.user))
            accounts_logger.info(
                "Account '%s' [id=%d] plan changed to '%s' [id=%d]" % (self.user, self.user.pk, plan, plan.pk))
            status = True
        else:
            # Processing standard account extending procedure
            if self.plan == plan:
                status = True
            else:
                # This should not ever happen (as this case should be managed by plan change request)
                # but just in case we consider a case when user has a different plan
                if not self.plan.is_free() and self.expire is None:
                    status = True
                elif not self.plan.is_free() and self.expire > date.today():
                    status = False
                    accounts_logger.warning("Account '%s' [id=%d] plan NOT changed to '%s' [id=%d]" % (
                        self.user, self.user.pk, plan, plan.pk))
                else:
                    status = True
                    account_change_plan.send(sender=self, user=self.user)
                    self.plan = plan

            if status:
                self.expire = expire
                self.save()
                accounts_logger.info("Account '%s' [id=%d] has been extended by %d days using plan '%s' [id=%d]" % (
                    self.user, self.user.pk, pricing.period, plan, plan.pk))
                if getattr(settings, 'PLANS_SEND_EMAILS_PLAN_EXTENDED', True):
                    mail_context = {'user': self.user,
                                    'userplan': self,
                                    'plan': plan,
                                    'pricing': pricing}
                    send_template_email([self.user.email], 'mail/extend_account_title.txt',
                                        'mail/extend_account_body.txt',
                                        mail_context, get_user_language(self.user))

        if status:
            self.clean_activation()

        return status

    def expire_account(self):
        """manages account expiration"""

        self.deactivate()

        accounts_logger.info(
            "Account '%s' [id=%d] has expired" % (self.user, self.user.pk))

        mail_context = {'user': self.user, 'userplan': self}
        send_template_email([self.user.email], 'mail/expired_account_title.txt', 'mail/expired_account_body.txt',
                            mail_context, get_user_language(self.user))

        account_expired.send(sender=self, user=self.user)

    def remind_expire_soon(self):
        """reminds about soon account expiration"""

        mail_context = {
            'user': self.user,
            'userplan': self,
            'days': self.days_left()
        }
        send_template_email([self.user.email], 'mail/remind_expire_title.txt', 'mail/remind_expire_body.txt',
                            mail_context, get_user_language(self.user))

    @classmethod
    def create_for_user(cls, user):
        default_plan = Plan.get_default_plan()
        if default_plan is not None:
            return UserPlan.objects.create(
                user=user,
                plan=default_plan,
                active=False,
                expire=None,
            )

    @classmethod
    def create_for_users_without_plan(cls):
        userplans = get_user_model().objects.filter(userplan=None)
        for user in userplans:
            UserPlan.create_for_user(user)
        return userplans

    def get_current_plan(self):
        """ Tiny helper, very usefull in templates """
        return Plan.get_current_plan(self.user)


class RecurringUserPlan(models.Model):
    """
    OneToOne model associated with UserPlan that stores information about the plan recurrence.

    More about recurring payments in docs.
    """
    user_plan = models.OneToOneField('UserPlan', on_delete=models.CASCADE, related_name='recurring')
    token = models.CharField(
        _('recurring token'),
        help_text=_('Token, that will be used for payment renewal. Depends on used payment provider'),
        max_length=255,
        default=None,
        null=True,
        blank=True,
    )
    payment_provider = models.CharField(
        _('payment provider'),
        help_text=_('Provider, that will be used for payment renewal'),
        max_length=255,
        default=None,
        null=True,
        blank=True,
    )
    pricing = models.ForeignKey('Pricing', help_text=_('Recurring pricing'), default=None,
                                null=True, blank=True, on_delete=models.CASCADE)
    amount = models.DecimalField(
        _('amount'), max_digits=7, decimal_places=2, db_index=True, null=True, blank=True)
    tax = models.DecimalField(_('tax'), max_digits=4, decimal_places=2, db_index=True, null=True,
                              blank=True)  # Tax=None is when tax is not applicable
    currency = models.CharField(_('currency'), max_length=3)
    has_automatic_renewal = models.BooleanField(
        _('has automatic plan renewal'),
        help_text=_(
            'Automatic renewal is enabled for associated plan. '
            'If False, the plan renewal can be still initiated by user.',
        ),
        default=False,
    )
    card_expire_year = models.IntegerField(null=True, blank=True)
    card_expire_month = models.IntegerField(null=True, blank=True)
    card_masked_number = models.CharField(null=True, blank=True, max_length=255)

    def create_renew_order(self):
        """
        Create order for plan renewal
        """
        userplan = self.user_plan
        return Order.objects.create(
            user=userplan.user,
            plan=userplan.plan,
            pricing=userplan.recurring.pricing,
            amount=userplan.recurring.amount,
            tax=userplan.recurring.tax,
            currency=userplan.recurring.currency,
        )


class Pricing(models.Model):
    """
    Type of plan period that could be purchased (e.g. 10 days, month, year, etc)
    """
    name = models.CharField(_('name'), max_length=100)
    period = models.PositiveIntegerField(
        _('period'), default=30, null=True, blank=True, db_index=True)
    url = models.URLField(max_length=200, blank=True, help_text=_(
        'Optional link to page with more information (for clickable pricing table headers)'))

    class Meta:
        ordering = ('period',)
        verbose_name = _("Pricing")
        verbose_name_plural = _("Pricings")

    def __str__(self):
        return "%s (%d " % (self.name, self.period) + "%s)" % _("days")


class Quota(OrderedModel):
    """
    Single countable or boolean property of system (limitation).
    """
    codename = models.CharField(
        _('codename'), max_length=50, unique=True, db_index=True)
    name = models.CharField(_('name'), max_length=100)
    unit = models.CharField(_('unit'), max_length=100, blank=True)
    description = models.TextField(_('description'), blank=True)
    is_boolean = models.BooleanField(_('is boolean'), default=False)
    url = models.CharField(max_length=200, blank=True, help_text=_(
        'Optional link to page with more information (for clickable pricing table headers)'))

    class Meta:
        ordering = ('order',)
        verbose_name = _("Quota")
        verbose_name_plural = _("Quotas")

    def __str__(self):
        return "%s" % (self.codename, )


class PlanPricingManager(models.Manager):
    def get_queryset(self):
        return super(PlanPricingManager, self).get_queryset().select_related('plan', 'pricing')


class PlanPricing(models.Model):
    plan = models.ForeignKey('Plan', on_delete=models.CASCADE)
    pricing = models.ForeignKey('Pricing', on_delete=models.CASCADE)
    price = models.DecimalField(max_digits=7, decimal_places=2, db_index=True)
    order = models.IntegerField(default=0, null=False, blank=False)
    has_automatic_renewal = models.BooleanField(
        _('has automatic renewal'),
        help_text=_('Use automatic renewal if possible?'),
        default=False,
    )

    objects = PlanPricingManager()

    class Meta:
        ordering = ('order', 'pricing__period', )
        verbose_name = _("Plan pricing")
        verbose_name_plural = _("Plans pricings")

    def __str__(self):
        return "%s %s" % (self.plan.name, self.pricing)


class PlanQuotaManager(models.Manager):
    def get_queryset(self):
        return super(PlanQuotaManager, self).get_queryset().select_related('plan', 'quota')


class PlanQuota(models.Model):
    plan = models.ForeignKey('Plan', on_delete=models.CASCADE)
    quota = models.ForeignKey('Quota', on_delete=models.CASCADE)
    value = models.IntegerField(default=1, null=True, blank=True)

    objects = PlanQuotaManager()

    class Meta:
        verbose_name = _("Plan quota")
        verbose_name_plural = _("Plans quotas")


class Order(models.Model):
    """
    Order in this app supports only one item per order. This item is defined by
    plan and pricing attributes. If both are defined the order represents buying
    an account extension.

    If only plan is provided (with pricing set to None) this means that user purchased
    a plan upgrade.
    """
    STATUS = Enumeration([
        (1, 'NEW', pgettext_lazy('Order status', 'new')),
        (2, 'COMPLETED', pgettext_lazy('Order status', 'completed')),
        (3, 'NOT_VALID', pgettext_lazy('Order status', 'not valid')),
        (4, 'CANCELED', pgettext_lazy('Order status', 'canceled')),
        (5, 'RETURNED', pgettext_lazy('Order status', 'returned')),

    ])

    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name=_('user'), on_delete=models.CASCADE)
    flat_name = models.CharField(max_length=200, blank=True, null=True)
    plan = models.ForeignKey('Plan', verbose_name=_(
        'plan'), related_name="plan_order", on_delete=models.CASCADE)
    pricing = models.ForeignKey('Pricing', blank=True, null=True, verbose_name=_(
        'pricing'), on_delete=models.CASCADE)  # if pricing is None the order is upgrade plan, not buy new pricing
    created = models.DateTimeField(_('created'), db_index=True)
    completed = models.DateTimeField(
        _('completed'), null=True, blank=True, db_index=True)
    plan_extended_from = models.DateField(
        _('plan extended from'),
        help_text=_('The plan was extended from this date'),
        null=True,
        blank=True,
    )
    plan_extended_until = models.DateField(
        _('plan extended until'),
        help_text=('The plan was extended until this date'),
        null=True,
        blank=True,
    )
    amount = models.DecimalField(
        _('amount'), max_digits=7, decimal_places=2, db_index=True)
    tax = models.DecimalField(_('tax'), max_digits=4, decimal_places=2, db_index=True, null=True,
                              blank=True)  # Tax=None is when tax is not applicable
    currency = models.CharField(_('currency'), max_length=3, default='EUR')
    status = models.IntegerField(
        _('status'), choices=STATUS, default=STATUS.NEW)

    def save(self, force_insert=False, force_update=False, using=None, update_fields=None):
        if self.created is None:
            self.created = now()
        return super(Order, self).save(force_insert, force_update, using)

    def __str__(self):
        return _("Order #%(id)d") % {'id': self.id}

    @property
    def name(self):
        """
        Support for two kind of Order names:
        * (preferred) dynamically generated from Plan and Pricing (if flatname is not provided) (translatable)
        * (legacy) just return flat name, which is any text (not translatable)

        Flat names are only introduced for legacy system support, when you need to migrate old orders into
        django-plans and you cannot match Plan&Pricings convention.
        """
        if self.flat_name:
            return self.flat_name
        else:
            return "%s %s %s " % (
                _('Plan'), self.plan.name, "(upgrade)" if self.pricing is None else '- %s' % self.pricing)

    def is_ready_for_payment(self):
        return self.status == self.STATUS.NEW and (now() - self.created).days < getattr(
            settings, 'PLANS_ORDER_EXPIRATION', 14)

    def get_plan_extended_from(self):
        return self.user.userplan.get_plan_extended_from(self.plan)

    def get_plan_extended_until(self):
        return self.user.userplan.get_plan_extended_until(self.plan, self.pricing)

    def complete_order(self):
        if self.completed is None:
            self.plan_extended_from = self.get_plan_extended_from()
            status = self.user.userplan.extend_account(self.plan, self.pricing)
            self.plan_extended_until = self.user.userplan.expire
            self.completed = now()
            if status:
                self.status = Order.STATUS.COMPLETED
            else:
                self.status = Order.STATUS.NOT_VALID
            self.save()
            order_completed.send(self)
            return True
        else:
            return False

    def get_invoices_proforma(self):
        return Invoice.proforma.filter(order=self)

    def get_invoices(self):
        return Invoice.invoices.filter(order=self)

    def get_all_invoices(self):
        return self.invoice_set.order_by('issued', 'issued_duplicate', 'pk')

    def get_plan_pricing(self):
        return PlanPricing.objects.get(plan=self.plan, pricing=self.pricing)

    def tax_total(self):
        if self.tax is None:
            return Decimal('0.00')
        else:
            return self.total() - self.amount

    def total(self):
        if self.tax is not None:
            return (self.amount * (self.tax + 100) / 100).quantize(Decimal('1.00'))
        else:
            return self.amount

    def get_absolute_url(self):
        return reverse('order', kwargs={'pk': self.pk})

    class Meta:
        ordering = ('-created', )
        verbose_name = _("Order")
        verbose_name_plural = _("Orders")


class InvoiceManager(models.Manager):
    def get_queryset(self):
        return super(InvoiceManager, self).get_queryset().filter(type=Invoice.INVOICE_TYPES['INVOICE'])


class InvoiceProformaManager(models.Manager):
    def get_queryset(self):
        return super(InvoiceProformaManager, self).get_queryset().filter(type=Invoice.INVOICE_TYPES['PROFORMA'])


class InvoiceDuplicateManager(models.Manager):
    def get_queryset(self):
        return super(InvoiceDuplicateManager, self).get_queryset().filter(type=Invoice.INVOICE_TYPES['DUPLICATE'])


class Invoice(models.Model):
    """
    Single invoice document.
    """

    INVOICE_TYPES = Enumeration([
        (1, 'INVOICE', _('Invoice')),
        (2, 'DUPLICATE', _('Invoice Duplicate')),
        (3, 'PROFORMA', pgettext_lazy('proforma', 'Order confirmation')),

    ])

    objects = models.Manager()
    invoices = InvoiceManager()
    proforma = InvoiceProformaManager()
    duplicates = InvoiceDuplicateManager()

    class NUMBERING:
        """Used as a choices for settings.PLANS_INVOICE_COUNTER_RESET"""

        DAILY = 1
        MONTHLY = 2
        ANNUALLY = 3

    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name=_('user'), on_delete=models.CASCADE)
    order = models.ForeignKey('Order', verbose_name=_('order'), on_delete=models.CASCADE)
    number = models.IntegerField(db_index=True)
    full_number = models.CharField(max_length=200)
    type = models.IntegerField(
        choices=INVOICE_TYPES, default=INVOICE_TYPES.INVOICE, db_index=True)
    issued = models.DateField(db_index=True)
    issued_duplicate = models.DateField(db_index=True, null=True, blank=True)
    selling_date = models.DateField(db_index=True, null=True, blank=True)
    payment_date = models.DateField(db_index=True)
    unit_price_net = models.DecimalField(max_digits=7, decimal_places=2)
    quantity = models.IntegerField(default=1)
    total_net = models.DecimalField(max_digits=7, decimal_places=2)
    total = models.DecimalField(max_digits=7, decimal_places=2)
    tax_total = models.DecimalField(max_digits=7, decimal_places=2)
    tax = models.DecimalField(max_digits=4, decimal_places=2, db_index=True, null=True,
                              blank=True)  # Tax=None is whet tax is not applicable
    rebate = models.DecimalField(
        max_digits=4, decimal_places=2, default=Decimal(0))
    currency = models.CharField(max_length=3, default='EUR')
    item_description = models.CharField(max_length=200)
    buyer_name = models.CharField(max_length=200, verbose_name=_("Name"))
    buyer_street = models.CharField(max_length=200, verbose_name=_("Street"))
    buyer_zipcode = models.CharField(
        max_length=200, verbose_name=_("Zip code"))
    buyer_city = models.CharField(max_length=200, verbose_name=_("City"))
    buyer_country = CountryField(verbose_name=_("Country"), default='PL')
    buyer_tax_number = models.CharField(
        max_length=200, blank=True, verbose_name=_("TAX/VAT number"))
    shipping_name = models.CharField(max_length=200, verbose_name=_("Name"))
    shipping_street = models.CharField(
        max_length=200, verbose_name=_("Street"))
    shipping_zipcode = models.CharField(
        max_length=200, verbose_name=_("Zip code"))
    shipping_city = models.CharField(max_length=200, verbose_name=_("City"))
    shipping_country = CountryField(verbose_name=_("Country"), default='PL')
    require_shipment = models.BooleanField(default=False, db_index=True)
    issuer_name = models.CharField(max_length=200, verbose_name=_("Name"))
    issuer_street = models.CharField(max_length=200, verbose_name=_("Street"))
    issuer_zipcode = models.CharField(
        max_length=200, verbose_name=_("Zip code"))
    issuer_city = models.CharField(max_length=200, verbose_name=_("City"))
    issuer_country = CountryField(verbose_name=_("Country"), default='PL')
    issuer_tax_number = models.CharField(
        max_length=200, blank=True, verbose_name=_("TAX/VAT number"))

    class Meta:
        verbose_name = _("Invoice")
        verbose_name_plural = _("Invoices")

    def __str__(self):
        return self.full_number

    def get_absolute_url(self):
        return reverse('invoice_preview_html', kwargs={'pk': self.pk})

    def clean(self):
        if self.number is None:
            invoice_counter_reset = getattr(
                settings, 'PLANS_INVOICE_COUNTER_RESET', Invoice.NUMBERING.MONTHLY)

            # To avoid duplicates as well as gaps in the sequence, we are using django-sequences
            # to generate sequence number for each invoice
            # We keep the old sequence generating mechanism to get lower initial value,
            # so that the sequence will continue backward compatibly
            older_invoices = Invoice.objects.filter(type=self.type)
            if invoice_counter_reset == Invoice.NUMBERING.DAILY:
                invoice_counter_value = f"{self.issued.year}_{self.issued.month}_{self.issued.day}"
                older_invoices = older_invoices.filter(issued=self.issued)
            elif invoice_counter_reset == Invoice.NUMBERING.MONTHLY:
                invoice_counter_value = f"{self.issued.year}_{self.issued.month}"
                older_invoices = older_invoices.filter(
                    issued__year=self.issued.year,
                    issued__month=self.issued.month,
                )
            elif invoice_counter_reset == Invoice.NUMBERING.ANNUALLY:
                invoice_counter_value = f"{self.issued.year}"
                older_invoices = older_invoices.filter(issued__year=self.issued.year)
            else:
                raise ImproperlyConfigured(
                    "PLANS_INVOICE_COUNTER_RESET can be set only to these values: daily, monthly, yearly.")

            # get initial value for backward compatibility
            self.initial_number = getattr(older_invoices.order_by("number").last(), 'number', 0) + 1
            self.sequence_name = f"invoice_numbers_{self.type}_{invoice_counter_reset}_{invoice_counter_value}"

    def save(self, *args, **kwargs):
        with transaction.atomic():
            if self.number is None:
                self.number = get_next_value(self.sequence_name, initial_value=self.initial_number)
            super().save(*args, **kwargs)

        # We need to generate full number based on what invoice sequence number actually ended up in DB
        self.refresh_from_db()
        if self.full_number == "":
            self.full_number = self.get_full_number()
        super().save(update_fields=["full_number"])

    #    def validate_unique(self, exclude=None):
    #        super(Invoice, self).validate_unique(exclude)
    #        if self.type == Invoice.INVOICE_TYPES.INVOICE:
    #            if Invoice.objects.filter(order=self.order).count():
    #                raise ValidationError("Duplicate invoice for order")
    #        if self.type in (Invoice.INVOICE_TYPES.INVOICE, Invoice.INVOICE_TYPES.PROFORMA):
    #            pass

    def get_full_number(self):
        """
        Generates on the fly invoice full number from template provided by ``settings.PLANS_INVOICE_NUMBER_FORMAT``.
        ``Invoice`` object is provided as ``invoice`` variable to the template, therefore all object fields
        can be used to generate full number format.

        .. warning::

            This is only used to prepopulate ``full_number`` field on saving new invoice.
            To get invoice full number always use ``full_number`` field.

        :return: string (generated full number)
        """
        format = getattr(
            settings,
            "PLANS_INVOICE_NUMBER_FORMAT",
            "{{ invoice.number }}/"
            "{% ifequal invoice.type invoice.INVOICE_TYPES.PROFORMA %}PF{% else %}FV{% endifequal %}"
            "/{{ invoice.issued|date:'m/Y' }}",
        )
        return Template(format).render(Context({'invoice': self}))

    def set_issuer_invoice_data(self):
        """
        Fills models object with issuer data copied from ``settings.PLANS_INVOICE_ISSUER``

        :raise: ImproperlyConfigured
        """
        try:
            issuer = getattr(settings, 'PLANS_INVOICE_ISSUER')
        except Exception:
            raise ImproperlyConfigured(
                "Please set PLANS_INVOICE_ISSUER in order to make an invoice.")
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

        self.shipping_name = billing_info.shipping_name or billing_info.name
        self.shipping_street = billing_info.shipping_street or billing_info.street
        self.shipping_zipcode = billing_info.shipping_zipcode or billing_info.zipcode
        self.shipping_city = billing_info.shipping_city or billing_info.city
        # TODO: Should allow shipping to other country? Not think so
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
        if Site is not None:
            self.item_description = "%s - %s" % (
                Site.objects.get_current().name, order.name)
        else:
            self.item_description = order.name

    @classmethod
    def create(cls, order, invoice_type):
        language_code = get_user_language(order.user)

        if language_code is not None:
            translation.activate(language_code)

        try:
            billing_info = BillingInfo.objects.get(user=order.user)
        except BillingInfo.DoesNotExist:
            return

        day = date.today()
        pday = order.completed
        if invoice_type == Invoice.INVOICE_TYPES['PROFORMA']:
            pday = day + timedelta(days=14)

        invoice = cls(issued=day, selling_date=order.completed,
                      payment_date=pday)  # FIXME: 14 - this should set accordingly to ORDER_TIMEOUT in days
        invoice.type = invoice_type
        invoice.copy_from_order(order)
        invoice.set_issuer_invoice_data()
        invoice.set_buyer_invoice_data(billing_info)
        invoice.clean()
        invoice.save()
        if language_code is not None:
            translation.deactivate()

    def send_invoice_by_email(self):
        if self.type in getattr(settings, 'PLANS_SEND_EMAILS_DISABLED_INVOICE_TYPES', []):
            return

        language_code = get_user_language(self.user)

        if language_code is not None:
            translation.activate(language_code)
        mail_context = {'user': self.user,
                        'invoice_type': self.get_type_display(),
                        'invoice_number': self.get_full_number(),
                        'order': self.order.id,
                        'order_object': self.order,
                        'url': self.get_absolute_url(), }
        if language_code is not None:
            translation.deactivate()
        send_template_email([self.user.email], 'mail/invoice_created_title.txt', 'mail/invoice_created_body.txt',
                            mail_context, language_code)

    def is_UE_customer(self):
        return EUTaxationPolicy.is_in_EU(self.buyer_country.code)


# noinspection PyUnresolvedReferences
import plans.listeners  # noqa
