from django.contrib.auth.decorators import login_required, permission_required
from django.conf.urls.defaults import patterns, include, url
from django.views.generic import TemplateView
from django.views.generic.detail import DetailView
from plans.models import Invoice
from plans.views import PDFDetailView, CreateOrderView, OrderListView, InvoiceDetailView
from views import CurrentPlanView, UpgradePlanView, OrderView, BillingInfoRedirectView, BillingInfoCreateView, BillingInfoUpdateView, BillingInfoDeleteView

urlpatterns = patterns('',

    
    url(r'^account/$', login_required(CurrentPlanView.as_view()), name='current_plan'),
    url(r'^upgrade/$', login_required(UpgradePlanView.as_view()), name='upgrade_plan'),
    url(r'^upgrade/new/order/(?P<pk>\d+)/$', login_required(CreateOrderView.as_view()), name='create_order_plan'),

    url(r'^order/$', login_required(OrderListView.as_view()), name='order_list'),
    url(r'^order/(?P<pk>\d+)/$', login_required(OrderView.as_view()), name='order'),
    url(r'^billing/$', login_required(BillingInfoRedirectView.as_view()), name='billing_info'),
    url(r'^billing/create/$', login_required(BillingInfoCreateView.as_view()), name='billing_info_create'),
    url(r'^billing/update/$', login_required(BillingInfoUpdateView.as_view()), name='billing_info_update'),
    url(r'^billing/delete/$', login_required(BillingInfoDeleteView.as_view()), name='billing_info_delete'),
    url(r'^invoice/(?P<pk>\d+)/preview/html/$', login_required(InvoiceDetailView.as_view()), name='invoice_preview_html'),
    url(r'^invoice/(?P<pk>\d+)/preview/pdf/$', login_required(PDFDetailView.as_view(queryset=Invoice.objects.all(), template_name='plans/invoice_preview.html')), name='invoice_preview_pdf'),

    
    
    
    # url(r'^payment/', login_required(OrderPaymentView.as_view()), name='order_payment'),



)
