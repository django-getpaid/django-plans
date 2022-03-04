import warnings
from decimal import Decimal
from itertools import chain

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ImproperlyConfigured
from django.db.models import Q
from django.http import Http404, HttpResponseForbidden, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse, reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views.generic import CreateView, RedirectView, TemplateView, View
from django.views.generic.detail import (DetailView, SingleObjectMixin,
                                         SingleObjectTemplateResponseMixin)
from django.views.generic.edit import (DeleteView, FormView, ModelFormMixin,
                                       ProcessFormView)
from django.views.generic.list import ListView
from next_url_mixin.mixin import NextUrlMixin

from plans.base.models import (AbstractBillingInfo, AbstractInvoice,
                               AbstractOrder, AbstractPlan,
                               AbstractPlanPricing, AbstractQuota,
                               AbstractUserPlan)
from plans.forms import BillingInfoForm, CreateOrderForm, FakePaymentsForm
from plans.importer import import_name
from plans.mixins import LoginRequired
from plans.signals import order_started
from plans.utils import get_currency
from plans.validators import plan_validation

UserPlan = AbstractUserPlan.get_concrete_model()
PlanPricing = AbstractPlanPricing.get_concrete_model()
Plan = AbstractPlan.get_concrete_model()
Order = AbstractOrder.get_concrete_model()
BillingInfo = AbstractBillingInfo.get_concrete_model()
Quota = AbstractQuota.get_concrete_model()
Invoice = AbstractInvoice.get_concrete_model()


class AccountActivationView(LoginRequired, TemplateView):
    template_name = 'plans/account_activation.html'

    def get_context_data(self, **kwargs):
        if self.request.user.userplan.active is True or self.request.user.userplan.is_expired():
            raise Http404()

        context = super(AccountActivationView, self).get_context_data(**kwargs)
        errors = self.request.user.userplan.clean_activation()

        if errors['required_to_activate']:
            context['SUCCESSFUL'] = False
        else:
            context['SUCCESSFUL'] = True
            messages.success(self.request, _("Your account is now active"))

        for error in errors['required_to_activate']:
            messages.error(self.request, error)
        for error in errors['other']:
            messages.warning(self.request, error)

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


class PlanTableViewBase(PlanTableMixin, ListView):
    model = Plan
    context_object_name = "plan_list"

    def get_queryset(self):
        queryset = super(PlanTableViewBase, self).get_queryset().prefetch_related('planpricing_set__pricing',
                                                                                  'planquota_set__quota')
        if self.request.user.is_authenticated:
            queryset = queryset.filter(
                Q(available=True, visible=True) & (
                    Q(customized=self.request.user) | Q(customized__isnull=True)
                )
            )
        else:
            queryset = queryset.filter(Q(available=True, visible=True) & Q(customized__isnull=True))
        return queryset

    def get_context_data(self, **kwargs):
        context = super(PlanTableViewBase, self).get_context_data(**kwargs)

        if self.request.user.is_authenticated:
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
        context['CURRENCY'] = settings.PLANS_CURRENCY

        return context


class CurrentPlanView(LoginRequired, PlanTableViewBase):
    template_name = "plans/current.html"

    def get_queryset(self):
        return Plan.objects.filter(userplan__user=self.request.user).prefetch_related('planpricing_set__pricing',
                                                                                      'planquota_set__quota')


class UpgradePlanView(LoginRequired, PlanTableViewBase):
    template_name = "plans/upgrade.html"


class PricingView(PlanTableViewBase):
    template_name = "plans/pricing.html"


class ChangePlanView(LoginRequired, View):
    """
    A view for instant changing user plan when it does not require additional payment.
    Plan can be changed without payment when:
    * user can enable this plan (it is available & visible and if it is customized it is for him,
    * plan is different from the current one that user have,
    * within current change plan policy this does not require any additional payment (None)

    It always redirects to ``upgrade_plan`` url as this is a potential only one place from
    where change plan could be invoked.
    """

    def get(self, request, *args, **kwargs):
        return HttpResponseRedirect(reverse('upgrade_plan'))

    def post(self, request, *args, **kwargs):
        plan = get_object_or_404(Plan, Q(pk=kwargs['pk']) & Q(available=True, visible=True) & (
            Q(customized=request.user) | Q(customized__isnull=True)))
        if request.user.userplan.plan != plan:
            policy = import_name(
                getattr(settings, 'PLANS_CHANGE_POLICY', 'plans.plan_change.StandardPlanChangePolicy'))()

            period = request.user.userplan.days_left()
            price = policy.get_change_price(request.user.userplan.plan, plan, period)

            if price is None:
                request.user.userplan.extend_account(plan, None)
                messages.success(request, _("Your plan has been successfully changed"))
            else:
                return HttpResponseForbidden()
        return HttpResponseRedirect(reverse('upgrade_plan'))


class CreateOrderView(LoginRequired, CreateView):
    template_name = "plans/create_order.html"
    form_class = CreateOrderForm

    def recalculate(self, amount, billing_info):
        """
        Calculates and return pre-filled Order
        """
        order = Order(pk=-1)
        order.recalculate(amount, billing_info, self.request)
        return order

    def validate_plan(self, plan):
        validation_errors = plan_validation(self.request.user, plan)
        if validation_errors['required_to_activate'] or validation_errors['other']:
            messages.error(self.request, _(
                "The selected plan is insufficient for your account. "
                "Your account will not be activated or will not work fully after completing this order."
                "<br><br>Following limits will be exceeded: <ul><li>%(reasons)s</ul>") % {
                'reasons': '<li>'.join(chain(validation_errors['required_to_activate'],
                                             validation_errors['other'])),
            })

    def get_all_context(self):
        """
        Retrieves Plan and Pricing for current order creation
        """
        self.plan_pricing = get_object_or_404(PlanPricing.objects.all().select_related('plan', 'pricing'),
                                              Q(pk=self.kwargs['pk']) & Q(plan__available=True) & (
                                                  Q(plan__customized=self.request.user) | Q(
                                                      plan__customized__isnull=True)))

        # User is not allowed to create new order for Plan when he has different Plan
        # unless it's a free plan. Otherwise, the should use Plan Change View for this
        # kind of action
        if not self.request.user.userplan.is_expired() \
                and not self.request.user.userplan.plan.is_free() \
                and self.request.user.userplan.plan != self.plan_pricing.plan:
            raise Http404

        self.plan = self.plan_pricing.plan
        self.pricing = self.plan_pricing.pricing

    def get_billing_info(self):
        try:
            return self.request.user.billinginfo
        except BillingInfo.DoesNotExist:
            return None

    def get_price(self):
        return self.plan_pricing.price

    def get_context_data(self, **kwargs):
        context = super(CreateOrderView, self).get_context_data(**kwargs)
        self.get_all_context()
        context['billing_info'] = self.get_billing_info()

        order = self.recalculate(self.get_price() or Decimal('0.0'), context['billing_info'])
        order.plan = self.plan_pricing.plan
        order.pricing = self.plan_pricing.pricing
        order.currency = get_currency()
        order.user = self.request.user
        context['object'] = order

        self.validate_plan(order.plan)
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
        self.plan = get_object_or_404(Plan, Q(pk=self.kwargs['pk']) & Q(available=True, visible=True) & (
            Q(customized=self.request.user) | Q(customized__isnull=True)))
        self.pricing = None

    def get_policy(self):
        policy_class = getattr(settings, 'PLANS_CHANGE_POLICY', 'plans.plan_change.StandardPlanChangePolicy')
        return import_name(policy_class)()

    def get_price(self):
        policy = self.get_policy()
        userplan = self.request.user.userplan

        if userplan.expire is not None:
            period = self.request.user.userplan.days_left()
        else:
            # Use the default period of the new plan
            period = 30

        return policy.get_change_price(self.request.user.userplan.plan, self.plan, period)

    def get_context_data(self, **kwargs):
        context = super(CreateOrderView, self).get_context_data(**kwargs)
        self.get_all_context()

        price = self.get_price()
        context['plan'] = self.plan
        context['billing_info'] = self.get_billing_info()
        if price is None:
            context['FREE_ORDER'] = True
            price = 0
        order = self.recalculate(price, context['billing_info'])
        order.pricing = None
        order.plan = self.plan
        order.user = self.request.user
        context['billing_info'] = context['billing_info']
        context['object'] = order
        self.validate_plan(order.plan)
        return context


class OrderView(LoginRequired, DetailView):
    model = Order

    def get_queryset(self):
        return super(OrderView, self).get_queryset().filter(user=self.request.user).select_related('plan', 'pricing', )


class OrderListView(LoginRequired, ListView):
    model = Order
    paginate_by = 10

    def get_context_data(self, **kwargs):
        context = super(OrderListView, self).get_context_data(**kwargs)
        self.CURRENCY = getattr(settings, 'PLANS_CURRENCY', None)
        if len(self.CURRENCY) != 3:
            raise ImproperlyConfigured('PLANS_CURRENCY should be configured as 3-letter currency code.')
        context['CURRENCY'] = self.CURRENCY
        return context

    def get_queryset(self):
        return super(OrderListView, self).get_queryset().filter(user=self.request.user).select_related('plan',
                                                                                                       'pricing', )


class OrderPaymentReturnView(LoginRequired, DetailView):
    """
    This view is a fallback from any payments processor. It allows just to set additional message
    context and redirect to Order view itself.
    """
    model = Order
    status = None

    def render_to_response(self, context, **response_kwargs):
        if self.status == 'success':
            messages.success(self.request,
                             _('Thank you for placing a payment. It will be processed as soon as possible.'))
        elif self.status == 'failure':
            messages.error(self.request, _('Payment was not completed correctly. Please repeat payment process.'))

        return HttpResponseRedirect(self.object.get_absolute_url())

    def get_queryset(self):
        return super(OrderPaymentReturnView, self).get_queryset().filter(user=self.request.user)


class SuccessUrlMixin():
    def get_success_url(self):
        messages.success(self.request, _('Billing info has been updated successfuly.'))
        return reverse('billing_info')


class CreateOrUpdateView(
    SingleObjectTemplateResponseMixin, ModelFormMixin, ProcessFormView
):
    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        return super().post(request, *args, **kwargs)


class BillingInfoCreateOrUpdateView(NextUrlMixin, SuccessUrlMixin, LoginRequired, CreateOrUpdateView):
    form_class = BillingInfoForm
    template_name = 'plans/billing_info_create_or_update.html'

    def get_object(self):
        try:
            return self.request.user.billinginfo
        except (AttributeError, BillingInfo.DoesNotExist):
            return None

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update(request=self.request)
        return kwargs


class RedirectToBilling(RedirectView):
    url = reverse_lazy('billing_info')
    permanent = False
    query_string = True

    def get_redirect_url(self, *args, **kwargs):
        warnings.warn(
            "This view URL is deprecated. Use plain billing_info instead.",
            DeprecationWarning,
        )
        return super().get_redirect_url(*args, **kwargs)


class BillingInfoDeleteView(LoginRequired, DeleteView):
    """
    Deletes billing data for user
    """
    template_name = 'plans/billing_info_delete.html'

    def get_object(self):
        try:
            return self.request.user.billinginfo
        except BillingInfo.DoesNotExist:
            raise Http404

    def get_success_url(self):
        messages.success(self.request, _('Billing info has been deleted.'))
        return reverse('billing_info')


class InvoiceDetailView(LoginRequired, DetailView):
    model = Invoice

    def get_template_names(self):
        return getattr(settings, 'PLANS_INVOICE_TEMPLATE', 'plans/invoices/PL_EN.html')

    def get_context_data(self, **kwargs):
        context = super(InvoiceDetailView, self).get_context_data(**kwargs)
        context['logo_url'] = getattr(settings, 'PLANS_INVOICE_LOGO_URL', None)
        context['auto_print'] = True
        return context

    def get_queryset(self):
        if self.request.user.is_superuser:
            return super(InvoiceDetailView, self).get_queryset().select_related('order')
        else:
            return super(InvoiceDetailView, self).get_queryset().filter(user=self.request.user).select_related('order')


class FakePaymentsView(LoginRequired, SingleObjectMixin, FormView):
    form_class = FakePaymentsForm
    model = Order
    template_name = 'plans/fake_payments.html'

    def get_success_url(self):
        return self.object.get_absolute_url()

    def get_queryset(self):
        return super(FakePaymentsView, self).get_queryset().filter(user=self.request.user)

    def dispatch(self, *args, **kwargs):
        if not getattr(settings, 'DEBUG', False):
            return HttpResponseForbidden('This view is accessible only in debug mode.')
        self.object = self.get_object()
        return super(FakePaymentsView, self).dispatch(*args, **kwargs)

    def form_valid(self, form):
        if int(form['status'].value()) == Order.STATUS.COMPLETED:
            self.object.complete_order()
            return HttpResponseRedirect(reverse('order_payment_success', kwargs={'pk': self.object.pk}))
        else:
            self.object.status = form['status'].value()
            self.object.save()
            return HttpResponseRedirect(reverse('order_payment_failure', kwargs={'pk': self.object.pk}))
