import datetime
from django.core.urlresolvers import reverse
from django.core.exceptions import ImproperlyConfigured
from django.shortcuts import get_object_or_404
from django.views.generic import TemplateView, FormView, RedirectView, CreateView, UpdateView
from django.db.models import Q
from django.http import Http404, HttpResponseRedirect
from django.conf import settings
from django.contrib import messages
from django.utils.translation import ugettext_lazy as _
from django.views.generic.detail import DetailView
#from django_xhtml2pdf.utils import render_to_pdf_response
from django.views.generic.edit import DeleteView, ModelFormMixin
from django.views.generic.list import ListView
import suds
import vatnumber
from plans.importer import import_name

from models import UserPlan, PlanQuota, PlanPricing, Plan, Order, BillingInfo
from forms import OrderForm, BillingInfoForm

from decimal import Decimal

# Create your views here.
from plans.forms import CreateOrderForm
from plans.models import Quota, Invoice
from plans.signals import order_started, account_activated
from plans.validators import account_full_validation

class AccountActivationView(TemplateView):
    template_name = 'plans/account_activation.html'

    def get_context_data(self, **kwargs):
        user_plan = self.request.user.userplan
        if user_plan.active == True or user_plan.expire < datetime.date.today():
            raise Http404()

        context = super(AccountActivationView, self).get_context_data(**kwargs)
        errors = account_full_validation(self.request.user)
        if errors:
            for error in errors:
                for e in error.messages:
                    messages.error(self.request, e)
            context['SUCCESSFUL'] = False
        else:
            user_plan.activate_account()
            messages.success(self.request, _("Your account is now active"))
            context['SUCCESSFUL'] = True
            account_activated.send(sender=self,user=self.request.user)
        return context

class PlanTableMixin(object):
    def get_plan_table(self, plan_list):
        """
        This method return a list in following order:
        [
            ( Quota1, [ Plan1Quota1, Plan2Quota1, ... , PlanNQuota1] ),
            ( Quota2, [ Plan1Quota2, Plan2Quota2, ... , PlanNQuota2] ),
            ...
            ( QuotaM, [ Plan1QuotaM, Plan2QuotaM, ... , PlanNQuotaM] ),
        ]

        This can be very easily printed as an HTML table element with quotas by row.

        Quotas are calculated based on ``plan_list``. These are all available quotas that are
        used by given plans. If any ``Plan`` does not have any of ``PlanQuota`` then value ``None``
        will be propagated to the data structure.

        """

        # Retrieve all quotas that are used by any ``Plan`` in ``plan_list``
        quota_list = Quota.objects.all().filter(planquota__plan__in = plan_list).distinct()

        # Create random access dict that for every ``Plan`` map ``Quota`` -> ``PlanQuota``
        plan_quotas_dic = {}
        for plan in plan_list:
            plan_quotas_dic[plan] = {}
            for plan_quota in plan.planquota_set.all():
                plan_quotas_dic[plan][plan_quota.quota] = plan_quota

        # Generate data structure described in method docstring, propagate ``None`` whenever
        # ``PlanQuota`` is not available for given ``Plan`` and ``Quota``
        return map(lambda quota: (quota,
                            map(lambda plan: plan_quotas_dic[plan].get(quota, None), plan_list)

            ), quota_list)



        
#class ExtendPlanView(CurrentPlanView):
#    template_name = "plans/extend.html"
#    def get_context_data(self, **kwargs):
#        context = super(ExtendPlanView, self).get_context_data(**kwargs)
#        context['pricings'] = PlanPricing.objects.select_related('pricing').filter(plan=context['userplan'])
#        context['form'] = OrderPlanForm()
#
#        return context

class UpgradePlanView(PlanTableMixin, ListView):
    template_name = "plans/upgrade.html"
    model = Plan
    context_object_name = "plan_list"

    def get_queryset(self):
        queryset = super(UpgradePlanView, self).get_queryset().prefetch_related('planpricing_set__pricing', 'planquota_set__quota')
        if self.request.user.is_authenticated():
            queryset = queryset.filter(
                            Q(available=True) & (
                                Q(customized = self.request.user) | Q(customized__isnull=True)
                                )
                            )
        else:
            queryset = queryset.filter(Q(available=True) & Q(customized__isnull=True))
        return queryset

    def get_context_data(self, **kwargs):
        context = super(UpgradePlanView, self).get_context_data(**kwargs)

        if self.request.user.is_authenticated():
            self.userplan = UserPlan.objects.select_related('plan').get(user=self.request.user)
            context['userplan'] = self.userplan
            try:
                context['current_userplan_index'] = list(self.object_list).index(self.userplan.plan)
            except ValueError:
                pass

        context['plan_table'] = self.get_plan_table(self.object_list)
        context['CURRENCY'] = settings.CURRENCY

        return context

class CurrentPlanView(UpgradePlanView):
    template_name = "plans/current.html"

    def get_queryset(self):
        return Plan.objects.filter(userplan__user=self.request.user).prefetch_related('planpricing_set__pricing', 'planquota_set__quota')
#
#    def get_context_data(self, **kwargs):
#        context = super(CurrentPlanView, self).get_context_data(**kwargs)
#




class CreateOrderView(CreateView):
    template_name = "plans/create_order.html"
    form_class = CreateOrderForm

    def recalculate(self, amount, tax, billing_info):
        """
        Method calculates order details
        """
        self.amount = amount
        self.tax = tax

        #checking if TAX is notapplicable via VIES

        VAT_COUNTRY = getattr(settings, 'VAT_COUNTRY', None)

        if billing_info and VAT_COUNTRY is not None and VAT_COUNTRY != billing_info.country and len(billing_info.tax_number) > 4 :
            vies_session_key = "vies %s %s" % (billing_info.country, billing_info.tax_number)
            vies = self.request.session.get(vies_session_key, None)
            if vies is None:
                try:
                    vies = vatnumber.check_vies(billing_info.tax_number)
                except suds.WebFault:
                    pass
                self.request.session['vies_session_key'] = vies

            if vies :
                self.tax = None

        if self.tax is not None:
            self.tax_total = (self.amount * (self.tax) / 100).quantize(Decimal('1.00'))
        else:
            self.tax_total = None

        if self.tax_total is None:
            self.total = self.amount
        else:
            self.total = self.amount + self.tax_total

    def get_all_context(self):
        self.plan_pricing = get_object_or_404(PlanPricing.objects.all().select_related('plan', 'pricing'),
            Q(pk=self.kwargs['pk']) & Q(plan__available=True) & Q(plan=self.request.user_plan.plan) & ( Q(plan__customized = self.request.user) | Q(plan__customized__isnull=True)))

    def get_billing_info(self):
        try:
            self.billing_info = self.request.user.billinginfo
        except BillingInfo.DoesNotExist:
            self.billing_info = None

    def get_currency(self):
        self.CURRENCY = getattr(settings, 'CURRENCY', None)
        if len(self.CURRENCY) != 3:
            raise ImproperlyConfigured('CURRENCY should be configured as 3-letter currency code.')

    def get_tax(self):
        self.tax = getattr(settings, 'TAX', None)
        if type(self.tax) != Decimal:
            raise ImproperlyConfigured('TAX should be configured as Decimal instance.')

    def get_context_data(self, **kwargs):
        context = super(CreateOrderView, self).get_context_data(**kwargs)
        self.get_all_context()
        self.get_billing_info()
        self.get_currency()
        self.get_tax()

        self.recalculate(self.plan_pricing.price, self.tax, self.billing_info)
        context['plan_pricing'] = self.plan_pricing
        context['plan'] = self.plan_pricing.plan
        context['pricing'] = self.plan_pricing.pricing

        context['billing_info'] = self.billing_info
        context['CURRENCY'] = self.CURRENCY
        context['tax'] = self.tax
        context['amount'] = self.amount
        context['tax_total'] = self.tax_total
        context['total'] = self.total
        return context

    def form_valid(self, form):
        self.get_all_context()
        self.get_billing_info()
        self.get_currency()
        self.get_tax()

        self.recalculate(self.plan_pricing.price, self.tax, self.billing_info)

        self.object = form.save(commit=False)
        self.object.user = self.request.user
        self.object.plan = self.plan
        self.object.pricing = self.pricing
        self.object.amount = self.amount
        self.object.tax = self.tax
        self.object.currency = self.CURRENCY
        self.object.save()
        order_started.send(sender=self.object)
        return super(ModelFormMixin, self).form_valid(form)


class CreateOrderPlanChangeView(CreateOrderView):
    template_name = "plans/create_order.html"
    form_class = CreateOrderForm

    def get_all_context(self):
        self.plan = get_object_or_404(Plan, Q(pk=self.kwargs['pk']) & Q(available=True) & ( Q(customized = self.request.user) | Q(customized__isnull=True)))

    def get_policy(self):
        policy_class = getattr(settings, 'PLAN_CHANGE_POLICY', 'plans.plan_switch.StandardPlanChangePolicy')
        return import_name(policy_class)()

    def get_context_data(self, **kwargs):
        context = super(CreateOrderView, self).get_context_data(**kwargs)

        self.get_all_context()
        self.get_billing_info()
        self.get_currency()
        self.get_tax()

        self.policy = self.get_policy()
        self.period = (self.request.user_plan.expire - datetime.date.today()).days
        self.price = self.policy.get_change_price(self.request.user_plan.plan, self.plan, self.period)
        context['plan'] = self.plan
        if self.price is None:
            context['current_plan'] = self.request.user_plan.plan
            context['FREE_ORDER'] = True
        else:

            self.recalculate(self.price, self.tax, self.billing_info)
            context['plan_pricing'] = None

            context['pricing'] = None

            context['billing_info'] = self.billing_info
            context['CURRENCY'] = self.CURRENCY
            context['tax'] = self.tax
            context['amount'] = self.amount
            context['tax_total'] = self.tax_total
            context['total'] = self.total
        return context


class OrderView(DetailView):
    model = Order

    def get_context_data(self, **kwargs):
        context = super(OrderView, self).get_context_data(**kwargs)

        self.CURRENCY = getattr(settings, 'CURRENCY', None)
        if len( self.CURRENCY) != 3:
            raise ImproperlyConfigured('CURRENCY should be configured as 3-letter currency code.')
        context['CURRENCY'] = self.CURRENCY
        context['plan'] = self.object.plan
        context['pricing'] = self.object.pricing
        context['tax'] = self.object.tax
        context['amount'] = self.object.amount
        context['tax_total'] = self.object.total() - self.object.amount
        context['total'] = self.object.total()

        context['invoices_proforma'] = self.object.get_invoices_proforma()
        context['invoices'] = self.object.get_invoices()

        context['printable_documents'] = self.object.get_all_invoices()
        context['INVOICE_TYPES'] = Invoice.INVOICE_TYPES
        return context

    def get_queryset(self):
        return super(OrderView, self).get_queryset().filter(user=self.request.user).select_related('plan', 'pricing', )

class OrderListView(ListView):
    model = Order
    paginate_by = 10
    def get_context_data(self, **kwargs):
        context = super(OrderListView, self).get_context_data(**kwargs)
        self.CURRENCY = getattr(settings, 'CURRENCY', None)
        if len( self.CURRENCY) != 3:
            raise ImproperlyConfigured('CURRENCY should be configured as 3-letter currency code.')
        context['CURRENCY'] = self.CURRENCY
        return context


    def get_queryset(self):
        return super(OrderListView, self).get_queryset().filter(user=self.request.user).select_related('plan', 'pricing', )

class OrderPaymentReturnView(DetailView):
    """
    This view is a fallback from any payments processor. It allows just to set additional message
    context and redirect to Order view itself.
    """
    model = Order
    status = None

    def render_to_response(self, context, **response_kwargs):
        if self.status == 'success':
            messages.success(self.request, _('Thank you for placing a payment. It will be processed as soon as possible.'))
        elif self.status == 'failure':
            messages.error(self.request, _('Payment was not completed correctly. Please repeat payment process.'))

        return HttpResponseRedirect(self.object.get_absolute_url())


    def get_queryset(self):
        return super(OrderPaymentReturnView, self).get_queryset().filter(user=self.request.user)


class BillingInfoRedirectView(RedirectView):
    """
    Checks if billing data for user exists and redirects to create or update view.
    """
    permanent = False
    def get_redirect_url(self, **kwargs):
        try:
            BillingInfo.objects.get(user=self.request.user)
        except BillingInfo.DoesNotExist:
            return reverse('billing_info_create')
        return reverse('billing_info_update')



class BillingInfoCreateView(CreateView):
    """
    Creates billing data for user
    """
    form_class = BillingInfoForm
    template_name = 'plans/billing_info_create.html'

    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.user = self.request.user
        self.object.save()
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url (self):
        messages.success(self.request, _('Billing info has been updated successfuly.'))
        return reverse('billing_info_update')
    

class BillingInfoUpdateView(UpdateView):
    """
    Updates billing data for user
    """
    model = BillingInfo
    form_class = BillingInfoForm
    template_name = 'plans/billing_info_update.html'

    def get_object(self):
        try:
            return self.request.user.billinginfo
        except BillingInfo.DoesNotExist:
            raise Http404
    
    def get_success_url (self):
        messages.success(self.request, _('Billing info has been updated successfuly.'))
        return reverse('billing_info_update')

class BillingInfoDeleteView(DeleteView):
    """
    Deletes billing data for user
    """
    template_name = 'plans/billing_info_delete.html'
    
    def get_object(self):
        try:
            return self.request.user.billinginfo
        except BillingInfo.DoesNotExist:
            raise Http404
    
    def get_success_url (self):
        messages.success(self.request, _('Billing info has been deleted.'))
        return reverse('billing_info_create')


class InvoiceDetailView(DetailView):
    template_name='plans/invoice_preview.html'
    model = Invoice

    def get_context_data(self, **kwargs):
        context = super(InvoiceDetailView, self).get_context_data(**kwargs)
        context['logo_url'] = getattr(settings, 'INVOICE_LOGO_URL', None)
        return context

    def get_queryset(self):
        return super(InvoiceDetailView, self).get_queryset().filter(user=self.request.user)


class PDFDetailView(DetailView):
    def render_to_response(self, context, **response_kwargs):
        return render_to_pdf_response(template_name=self.get_template_names()[0], context=context, pdfname=unicode(self.object).replace('/', '_'))