from django.conf import settings
from django.urls import path

from plans.views import (AccountActivationView, BillingInfoCreateOrUpdateView,
                         BillingInfoDeleteView, ChangePlanView,
                         CreateOrderPlanChangeView, CreateOrderView,
                         CurrentPlanView, FakePaymentsView, InvoiceDetailView,
                         OrderListView, OrderPaymentReturnView, OrderView,
                         PricingView, RedirectToBilling, UpgradePlanView)

urlpatterns = [
    path('pricing/', PricingView.as_view(), name='pricing'),
    path('account/', CurrentPlanView.as_view(), name='current_plan'),
    path('account/activation/', AccountActivationView.as_view(), name='account_activation'),
    path('upgrade/', UpgradePlanView.as_view(), name='upgrade_plan'),
    path('order/extend/new/<int:pk>/', CreateOrderView.as_view(), name='create_order_plan'),
    path('order/upgrade/new/<int:pk>/', CreateOrderPlanChangeView.as_view(), name='create_order_plan_change'),
    path('change/<int:pk>/', ChangePlanView.as_view(), name='change_plan'),
    path('order/', OrderListView.as_view(), name='order_list'),
    path('order/<int:pk>/', OrderView.as_view(), name='order'),
    path('order/<int:pk>/payment/success/', OrderPaymentReturnView.as_view(status='success'),
         name='order_payment_success'),
    path('order/<int:pk>/payment/failure/', OrderPaymentReturnView.as_view(status='failure'),
         name='order_payment_failure'),
    # Redirect for backward compatibility:
    path('billing/create/', RedirectToBilling.as_view(), name='billing_info_create'),
    # Redirect for backward compatibility:
    path('billing/update/', RedirectToBilling.as_view(), name='billing_info_update'),
    path('billing/', BillingInfoCreateOrUpdateView.as_view(), name='billing_info'),
    path('billing/delete/', BillingInfoDeleteView.as_view(), name='billing_info_delete'),
    path('invoice/<int:pk>/preview/html/', InvoiceDetailView.as_view(), name='invoice_preview_html'),
]

if getattr(settings, 'DEBUG', False) or getattr(settings, 'ENABLE_FAKE_PAYMENTS', True):
    urlpatterns += [
        path('fakepayments/<int:pk>/', FakePaymentsView.as_view(), name='fake_payments'),
    ]
