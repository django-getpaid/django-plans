from django.contrib import admin
from models import UserPlan, Plan, PlanQuota, Quota, PlanPricing, Pricing, Order, BillingInfo
from ordered_model.admin import OrderedModelAdmin
from plans.models import Invoice

class PlanQuotaInline(admin.TabularInline):
    model = PlanQuota

class PlanPricingInline(admin.TabularInline):
    model = PlanPricing

class QuotaAdmin(OrderedModelAdmin):
    list_display = ('codename', 'name', 'description', 'unit', 'is_boolean', 'order', 'move_up_down_links', )

class PlanAdmin(OrderedModelAdmin):
    list_filter = ( 'available', 'customized' )
    list_display = ('name',   'description', 'customized', 'default', 'available', 'created', 'move_up_down_links')
    inlines = (PlanPricingInline, PlanQuotaInline)

    def queryset(self, request):
        return super(PlanAdmin, self).queryset(request).select_related('customized')


class BillingInfoAdmin(admin.ModelAdmin):
    list_display = ('user', 'name',  'street', 'zipcode', 'city', 'country')

class OrderAdmin(admin.ModelAdmin):
    list_filter = ( 'user', 'valid' )
    list_display = ('user', "created", "valid", "completed", "amount", "currency", "plan", "pricing")

    def queryset(self, request):
        return super(OrderAdmin, self).queryset(request).select_related('plan', 'pricing', 'user')


class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('full_number', "issued", "total_net", "currency", "tax", "buyer_name", "buyer_city", "buyer_tax_number")

admin.site.register(Quota, QuotaAdmin)
admin.site.register(Plan, PlanAdmin)
admin.site.register(UserPlan)
admin.site.register(Pricing)
admin.site.register(Order, OrderAdmin)
admin.site.register(BillingInfo, BillingInfoAdmin)
admin.site.register(Invoice, InvoiceAdmin)


