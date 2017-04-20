from django.conf import settings
from django.conf.urls import url

from plans.views import CreateOrderView, OrderListView, InvoiceDetailView, AccountActivationView, \
    OrderPaymentReturnView, CurrentPlanView, UpgradePlanView, OrderView, BillingInfoRedirectView, \
    BillingInfoCreateView, BillingInfoUpdateView, BillingInfoDeleteView, CreateOrderPlanChangeView, ChangePlanView, \
    PricingView, FakePaymentsView

urlpatterns = [
    url(r'^pricing/$', PricingView.as_view(), name='pricing'),
    url(r'^account/$', CurrentPlanView.as_view(), name='current_plan'),
    url(r'^account/activation/$', AccountActivationView.as_view(), name='account_activation'),
    url(r'^upgrade/$', UpgradePlanView.as_view(), name='upgrade_plan'),
    url(r'^order/extend/new/(?P<pk>\d+)/$', CreateOrderView.as_view(), name='create_order_plan'),
    url(r'^order/upgrade/new/(?P<pk>\d+)/$', CreateOrderPlanChangeView.as_view(), name='create_order_plan_change'),
    url(r'^change/(?P<pk>\d+)/$', ChangePlanView.as_view(), name='change_plan'),
    url(r'^order/$', OrderListView.as_view(), name='order_list'),
    url(r'^order/(?P<pk>\d+)/$', OrderView.as_view(), name='order'),
    url(r'^order/(?P<pk>\d+)/payment/success/$', OrderPaymentReturnView.as_view(status='success'),
        name='order_payment_success'),
    url(r'^order/(?P<pk>\d+)/payment/failure/$', OrderPaymentReturnView.as_view(status='failure'),
        name='order_payment_failure'),
    url(r'^billing/$', BillingInfoRedirectView.as_view(), name='billing_info'),
    url(r'^billing/create/$', BillingInfoCreateView.as_view(), name='billing_info_create'),
    url(r'^billing/update/$', BillingInfoUpdateView.as_view(), name='billing_info_update'),
    url(r'^billing/delete/$', BillingInfoDeleteView.as_view(), name='billing_info_delete'),
    url(r'^invoice/(?P<pk>\d+)/preview/html/$', InvoiceDetailView.as_view(), name='invoice_preview_html'),
]

if getattr(settings, 'DEBUG', False):
    urlpatterns += [
        url(r'^fakepayments/(?P<pk>\d+)/$', FakePaymentsView.as_view(), name='fake_payments'),
    ]
