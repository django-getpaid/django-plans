from copy import deepcopy

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.urls import reverse
from ordered_model.admin import OrderedModelAdmin
from django.utils.translation import ugettext_lazy as _
from django.utils.html import format_html

from .models import UserPlan, Plan, PlanQuota, Quota, PlanPricing, Pricing, Order, BillingInfo
from plans.models import Invoice


class UserLinkMixin(object):
    def user_link(self, obj):
        user_model = get_user_model()
        app_label = user_model._meta.app_label
        model_name = user_model._meta.model_name
        change_url = reverse('admin:%s_%s_change' % (app_label, model_name), args=(obj.user.id,))
        return format_html('<a href="{}">{}</a>', change_url, obj.user.username)

    user_link.short_description = 'User'
    user_link.allow_tags = True


class PlanQuotaInline(admin.TabularInline):
    model = PlanQuota


class PlanPricingInline(admin.TabularInline):
    model = PlanPricing


class QuotaAdmin(OrderedModelAdmin):
    list_display = [
        'codename', 'name', 'description', 'unit',
        'is_boolean', 'move_up_down_links',
    ]

    list_display_links = list_display


def copy_plan(modeladmin, request, queryset):
    """
    Admin command for duplicating plans preserving quotas and pricings.
    """
    for plan in queryset:
        plan_copy = deepcopy(plan)
        plan_copy.id = None
        plan_copy.available = False
        plan_copy.default = False
        plan_copy.created = None
        plan_copy.save(force_insert=True)

        for pricing in plan.planpricing_set.all():
            pricing.id = None
            pricing.plan = plan_copy
            pricing.save(force_insert=True)

        for quota in plan.planquota_set.all():
            quota.id = None
            quota.plan = plan_copy
            quota.save(force_insert=True)


copy_plan.short_description = _('Make a plan copy')


class PlanAdmin(OrderedModelAdmin):
    search_fields = ('name', 'customized__username', 'customized__email', )
    list_filter = ('available', 'visible')
    list_display = [
        'name', 'description', 'customized', 'default', 'available',
        'created', 'move_up_down_links'
    ]
    list_display_links = list_display
    inlines = (PlanPricingInline, PlanQuotaInline)
    list_select_related = True
    raw_id_fields = ('customized',)
    actions = [copy_plan, ]

    def queryset(self, request):
        return super(PlanAdmin, self).queryset(request).select_related(
            'customized'
        )


class BillingInfoAdmin(UserLinkMixin, admin.ModelAdmin):
    search_fields = ('user__username', 'user__email', 'tax_number', 'name')
    list_display = ('user', 'tax_number', 'name', 'street', 'zipcode', 'city', 'country')
    list_display_links = list_display
    list_select_related = True
    readonly_fields = ('user_link',)
    exclude = ('user',)


def make_order_completed(modeladmin, request, queryset):
    for order in queryset:
        order.complete_order()


make_order_completed.short_description = _('Make selected orders completed')


def make_order_invoice(modeladmin, request, queryset):
    for order in queryset:
        if Invoice.objects.filter(type=Invoice.INVOICE_TYPES['INVOICE'], order=order).count() == 0:
            Invoice.create(order, Invoice.INVOICE_TYPES['INVOICE'])


make_order_invoice.short_description = _('Make invoices for orders')


class InvoiceInline(admin.TabularInline):
    model = Invoice
    extra = 0
    raw_id_fields = (
        'user',
    )


class OrderAdmin(admin.ModelAdmin):
    list_filter = ('status', 'created', 'completed', 'plan__name', 'pricing')
    raw_id_fields = ('user',)
    search_fields = (
        'id', 'user__username', 'user__email', 'invoice__full_number'
    )
    list_display = (
        'id', 'name', 'created', 'user', 'status', 'completed',
        'tax', 'amount', 'currency', 'plan', 'pricing',
        'plan_extended_from', 'plan_extended_until',
    )
    list_display_links = list_display
    actions = [make_order_completed, make_order_invoice]
    inlines = (InvoiceInline, )

    def queryset(self, request):
        return super(OrderAdmin, self).queryset(request).select_related('plan', 'pricing', 'user')


class InvoiceAdmin(admin.ModelAdmin):
    search_fields = (
        'full_number', 'buyer_tax_number',
        'user__username', 'user__email'
    )
    list_filter = ('type', 'issued')
    list_display = (
        'full_number', 'issued', 'total_net', 'currency', 'user',
        'tax', 'buyer_name', 'buyer_city', 'buyer_tax_number'
    )
    list_display_links = list_display
    list_select_related = True
    raw_id_fields = ('user', 'order')


class UserPlanAdmin(UserLinkMixin, admin.ModelAdmin):
    list_filter = ('active', 'expire', 'plan__name', 'plan__available', 'plan__visible',)
    search_fields = ('user__username', 'user__email', 'plan__name',)
    list_display = ('user', 'plan', 'expire', 'active')
    list_display_links = list_display
    list_select_related = True
    readonly_fields = ['user_link', ]
    fields = ('user', 'user_link', 'plan', 'expire', 'active' )
    raw_id_fields = ['user', 'plan', ]


admin.site.register(Quota, QuotaAdmin)
admin.site.register(Plan, PlanAdmin)
admin.site.register(UserPlan, UserPlanAdmin)
admin.site.register(Pricing)
admin.site.register(Order, OrderAdmin)
admin.site.register(BillingInfo, BillingInfoAdmin)
admin.site.register(Invoice, InvoiceAdmin)
