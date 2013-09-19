from decimal import Decimal
from django.core.urlresolvers import reverse
from django.core.exceptions import ImproperlyConfigured
from django.shortcuts import get_object_or_404
from django.views.generic import TemplateView, RedirectView, CreateView, UpdateView, View
from django.db.models import Q
from django.http import Http404, HttpResponseRedirect, HttpResponseForbidden
from django.conf import settings
from django.contrib import messages
from django.utils.translation import ugettext_lazy as _
from django.views.generic.detail import DetailView
from django.views.generic.edit import DeleteView, ModelFormMixin
from django.views.generic.list import ListView
from plans.importer import import_name
from plans.models import UserPlan, PlanPricing, Plan, Order, BillingInfo
from plans.forms import CreateOrderForm, BillingInfoForm, BillingInfoWithoutShippingForm
from plans.models import Quota, Invoice
from plans.signals import order_started
from plans.validators import account_full_validation


class AccountActivationView(TemplateView):
    template_name = 'plans/account_activation.html'

    def get_context_data(self, **kwargs):
        if self.request.user.userplan.active == True or self.request.user.userplan.is_expired():
            raise Http404()

        context = super(AccountActivationView, self).get_context_data(**kwargs)
        errors = account_full_validation(self.request.user)
        if errors:
            for error in errors:
                for e in error.messages:
                    messages.error(self.request, e)
            context['SUCCESSFUL'] = False
        else:
            self.request.user.userplan.activate()
            messages.success(self.request, _("Your account is now active"))
            context['SUCCESSFUL'] = True

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
        quota_list = Quota.objects.all().filter(planquota__plan__in=plan_list).distinct()

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
            try:
                self.userplan = UserPlan.objects.select_related('plan').get(user=self.request.user)
            except UserPlan.DoesNotExist:
                self.userplan = None

            context['userplan'] = self.userplan

            try:
                context['current_userplan_index'] = list(self.object_list).index(self.userplan.plan)
            except (ValueError, AttributeError):
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


class ChangePlanView(View):
    """
    A view for instant changing user plan when it does not require additional payment.
    Plan can be changed without payment when:
    * user can enable this plan (it is available and if it is customized it is for him,
    * plan is different from the current one that user have,
    * within current change plan policy this does not require any additional payment (None)

    It always redirects to ``upgrade_plan`` url as this is a potential only one place from
    where change plan could be invoked.
    """

    def get(self, request, *args, **kwargs):
        return HttpResponseRedirect(reverse('upgrade_plan'))

    def post(self, request, *args, **kwargs):
        plan = get_object_or_404(Plan, Q(pk=kwargs['pk']) & Q(available=True) & ( Q(customized = request.user) | Q(customized__isnull=True)))
        if request.user.userplan.plan != plan:
            policy = import_name(getattr(settings, 'PLAN_CHANGE_POLICY', 'plans.plan_change.StandardPlanChangePolicy'))()

            period = request.user.userplan.days_left()
            price = policy.get_change_price(request.user.userplan.plan, plan, period)

            if price is None:
                request.user.userplan.extend_account(plan, None)
                messages.success(request, _("Your plan has been successfully changed"))
            else:
                return HttpResponseForbidden()
        return HttpResponseRedirect(reverse('upgrade_plan'))


class CreateOrderView(CreateView):
    template_name = "plans/create_order.html"
    form_class = CreateOrderForm

    def recalculate(self, amount, billing_info):
        """
        Calculates and return pre-filled Order
        """
        order = Order(pk=-1)
        order.amount = amount
        order.currency = self.get_currency()
        country = getattr(billing_info, 'country', None)
        if not country is None:
            country = country.code
        tax_number = getattr(billing_info, 'tax_number', None)

        # Calculating session can be complex task (e.g. VIES webservice call)
        # To ensure that once we get what tax we display to confirmation it will
        # not change, tax rate is cached for a given billing data (as it mainly depends on it)
        tax_session_key = "tax_%s_%s" % (tax_number, country)

        tax = self.request.session.get(tax_session_key)

        if tax:
            order.tax = tax[0] #retreiving tax as a tuple to avoid None problems
        else:
            taxation_policy = getattr(settings, 'TAXATION_POLICY' , None)
            if not taxation_policy:
                raise ImproperlyConfigured('TAXATION_POLICY is not set')
            taxation_policy = import_name(taxation_policy)
            order.tax = taxation_policy.get_tax_rate(tax_number, country)
            self.request.session[tax_session_key] = (order.tax, )

        return order

    def get_all_context(self):
        """
        Retrieves Plan and Pricing for current order creation
        """
        self.plan_pricing = get_object_or_404(PlanPricing.objects.all().select_related('plan', 'pricing'),
            Q(pk=self.kwargs['pk']) & Q(plan__available=True)  & ( Q(plan__customized = self.request.user) | Q(plan__customized__isnull=True)))


        # User is not allowed to create new order for Plan when he has different Plan
        # He should use Plan Change View for this kind of action
        if not self.request.user.userplan.is_expired() and self.request.user.userplan.plan != self.plan_pricing.plan:
            raise Http404

        self.plan = self.plan_pricing.plan
        self.pricing = self.plan_pricing.pricing

    def get_billing_info(self):
        try:
            return self.request.user.billinginfo
        except BillingInfo.DoesNotExist:
            return None

    def get_currency(self):
        CURRENCY = getattr(settings, 'CURRENCY', '')
        if len(CURRENCY) != 3:
            raise ImproperlyConfigured('CURRENCY should be configured as 3-letter currency code.')
        return CURRENCY

    def get_price(self):
        return self.plan_pricing.price

    def get_context_data(self, **kwargs):
        context = super(CreateOrderView, self).get_context_data(**kwargs)
        self.get_all_context()
        context['billing_info'] = self.get_billing_info()

        order = self.recalculate(self.plan_pricing.price, context['billing_info'])
        order.plan = self.plan_pricing.plan
        order.pricing = self.plan_pricing.pricing
        order.currency = self.get_currency()
        context['object'] = order
        return context

    def form_valid(self, form):
        self.get_all_context()
        order = self.recalculate(self.get_price() or Decimal('0.0'), self.get_billing_info())

        self.object = form.save(commit=False)
        self.object.user = self.request.user
        self.object.plan = self.plan
        self.object.pricing = self.pricing
        self.object.amount = order.amount
        self.object.tax = order.tax
        self.object.currency = order.currency
        self.object.save()
        order_started.send(sender=self.object)
        return super(ModelFormMixin, self).form_valid(form)


class CreateOrderPlanChangeView(CreateOrderView):
    template_name = "plans/create_order.html"
    form_class = CreateOrderForm

    def get_all_context(self):
        self.plan = get_object_or_404(Plan, Q(pk=self.kwargs['pk']) & Q(available=True) & ( Q(customized = self.request.user) | Q(customized__isnull=True)))
        self.pricing = None

    def get_policy(self):
        policy_class = getattr(settings, 'PLAN_CHANGE_POLICY', 'plans.plan_change.StandardPlanChangePolicy')
        return import_name(policy_class)()

    def get_price(self):
        policy = self.get_policy()
        period = self.request.user.userplan.days_left()
        return policy.get_change_price(self.request.user.userplan.plan, self.plan, period)

    def get_context_data(self, **kwargs):
        context = super(CreateOrderView, self).get_context_data(**kwargs)
        self.get_all_context()

        price = self.get_price()
        context['plan'] = self.plan
        context['billing_info'] = self.get_billing_info()
        if price is None:
            context['current_plan'] = self.request.user.userplan.plan
            context['FREE_ORDER'] = True
        else:
            order = self.recalculate(price, context['billing_info'])
            order.pricing = None
            order.plan = self.plan
            context['billing_info'] = context['billing_info']
            context['object'] = order
        return context


class OrderView(DetailView):
    model = Order

#    def get_context_data(self, **kwargs):
#        context = super(OrderView, self).get_context_data(**kwargs)
#
#        self.CURRENCY = getattr(settings, 'CURRENCY', None)
#        if len( self.CURRENCY) != 3:
#            raise ImproperlyConfigured('CURRENCY should be configured as 3-letter currency code.')
#        context['CURRENCY'] = self.CURRENCY
#
#        context['plan'] = self.object.plan
#        context['pricing'] = self.object.pricing
#        context['tax'] = self.object.tax
#        context['amount'] = self.object.amount
#        context['tax_total'] = self.object.total() - self.object.amount
#        context['total'] = self.object.total()
#
#        context['invoices_proforma'] = self.object.get_invoices_proforma()
#        context['invoices'] = self.object.get_invoices()
#
#        context['printable_documents'] = self.object.get_all_invoices()
#        context['INVOICE_TYPES'] = Invoice.INVOICE_TYPES
#        return context

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
    model = Invoice

    def get_template_names(self):
        return getattr(settings, 'INVOICE_TEMPLATE', 'plans/invoices/PL_EN.html')


    def get_context_data(self, **kwargs):
        context = super(InvoiceDetailView, self).get_context_data(**kwargs)
        context['logo_url'] = getattr(settings, 'INVOICE_LOGO_URL', None)
        context['auto_print'] = True
        return context

    def get_queryset(self):
        if self.request.user.is_superuser:
            return super(InvoiceDetailView, self).get_queryset()
        else:
            return super(InvoiceDetailView, self).get_queryset().filter(user=self.request.user)

