from copy import deepcopy

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core import urlresolvers
from ordered_model.admin import OrderedModelAdmin
from django.utils.translation import ugettext_lazy as _

from .models import UserPlan, Plan, PlanQuota, Quota, PlanPricing, Pricing, Order, BillingInfo
from plans.models import Invoice


class UserLinkMixin(object):
    def user_link(self, obj):
        change_url = urlresolvers.reverse('admin:auth_user_change', args=(obj.user.id,))
        return '<a href="%s">%s</a>' % (change_url, obj.user.get_username())

    user_link.short_description = 'User'
    user_link.allow_tags = True


class PlanQuotaInline(admin.TabularInline):
    model = PlanQuota


class PlanPricingInline(admin.TabularInline):
    model = PlanPricing


class QuotaAdmin(OrderedModelAdmin):
    list_display = ('codename', 'name', 'description', 'unit', 'is_boolean', 'move_up_down_links', )


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
    list_display = ('name', 'description', 'customized', 'default', 'available', 'created', 'move_up_down_links')
    inlines = (PlanPricingInline, PlanQuotaInline)
    list_select_related = True
    raw_id_fields = ('customized',)
    actions = [copy_plan, ]

    def queryset(self, request):
        return super(PlanAdmin, self).queryset(request).select_related('customized')


class BillingInfoAdmin(UserLinkMixin, admin.ModelAdmin):

    _user_model = get_user_model()
    try:
        _username_field = _user_model._meta.model.USERNAME_FIELD
    except:
        _username_field = "username"

    # TODO: is there a better approach?
    try:
        _email_field = _user_model._meta.get_field_by_name("email")
    except:
        _email_field = None

    if _email_field:
        search_fields = ('user__{0}'.format(_username_field), 'user__email', 'tax_number', 'name')
    else:
        search_fields = ('user__{0}'.format(_username_field), 'tax_number', 'name')

    list_display = ('user', 'tax_number', 'name', 'street', 'zipcode', 'city', 'country')
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


class OrderAdmin(admin.ModelAdmin):

    _user_model = get_user_model()
    try:
        _username_field = _user_model._meta.model.USERNAME_FIELD
    except:
        _username_field = "username"

    # TODO: is there a better approach?
    try:
        _email_field = _user_model._meta.get_field_by_name("email")
    except:
        _email_field = None

    list_filter = ('status', 'created', 'completed', 'plan__name', 'pricing')
    raw_id_fields = ('user',)

    if _email_field:
        search_fields = ('id', 'user__{0}'.format(_username_field), 'user__email')
    else:
        search_fields = ('id', 'user__{0}'.format(_username_field))

    list_display = (
        'id', 'name', 'created', 'user', 'status', 'completed', 'tax', 'amount', 'currency', 'plan', 'pricing')
    actions = [make_order_completed, make_order_invoice]
    inlines = (InvoiceInline, )

    def queryset(self, request):
        return super(OrderAdmin, self).queryset(request).select_related('plan', 'pricing', 'user')


class InvoiceAdmin(admin.ModelAdmin):
    search_fields = ('full_number', 'buyer_tax_number', 'user__username', 'user__email')
    list_filter = ('type', 'issued')
    list_display = (
        'full_number', 'issued', 'total_net', 'currency', 'user', 'tax', 'buyer_name', 'buyer_city', 'buyer_tax_number')
    list_select_related = True
    raw_id_fields = ('user', 'order')


class UserPlanAdmin(UserLinkMixin, admin.ModelAdmin):

    _user_model = get_user_model()
    try:
        _username_field = _user_model._meta.model.USERNAME_FIELD
    except:
        _username_field = "username"

    # TODO: is there a better approach?
    try:
        _email_field = _user_model._meta.get_field_by_name("email")
    except:
        _email_field = None

    list_filter = ('active', 'expire', 'plan__name', 'plan__available', 'plan__visible',)

    if _email_field:
        search_fields = ('user__{0}'.format(_username_field), 'user__email', 'plan__name',)
    else:
        search_fields = ('user__{0}'.format(_username_field), 'plan__name',)

    list_display = ('user', 'plan', 'expire', 'active')
    list_select_related = True
    readonly_fields = ['user_link', ]
    fields = ('user_link', 'plan', 'expire', 'active' )
    raw_id_fields = ['plan', ]


admin.site.register(Quota, QuotaAdmin)
admin.site.register(Plan, PlanAdmin)
admin.site.register(UserPlan, UserPlanAdmin)
admin.site.register(Pricing)
admin.site.register(Order, OrderAdmin)
admin.site.register(BillingInfo, BillingInfoAdmin)
admin.site.register(Invoice, InvoiceAdmin)


