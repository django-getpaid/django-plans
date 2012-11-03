from django.contrib import admin
from models import UserPlan, Plan, PlanQuota, Quota, PlanPricing, Pricing, Order, BillingInfo
from ordered_model.admin import OrderedModelAdmin
from plans.models import Invoice

class PlanQuotaInline(admin.TabularInline):
    model = PlanQuota

class PlanPricingInline(admin.TabularInline):
    model = PlanPricing

class QuotaAdmin(OrderedModelAdmin):
    list_display = ('codename', 'name', 'description', 'unit', 'is_boolean',  'move_up_down_links', )

class PlanAdmin(OrderedModelAdmin):
    search_fields = ('customized__username', 'customized__email', )
    list_filter = ( 'available',  )
    list_display = ('name',   'description', 'customized', 'default', 'available', 'created', 'move_up_down_links')
    inlines = (PlanPricingInline, PlanQuotaInline)
    list_select_related = True

    def queryset(self, request):
        return super(PlanAdmin, self).queryset(request).select_related('customized')


class BillingInfoAdmin(admin.ModelAdmin):
    search_fields = ('user__username', 'user__email')
    list_display = ('user', 'name',  'street', 'zipcode', 'city', 'country')
    list_select_related = True

class OrderAdmin(admin.ModelAdmin):
    list_filter = ('status', "plan")
    search_fields = ('id', 'user__username', 'user__email')
    list_display = ("id", "created", "user", "status", "completed", "amount", "currency", "plan", "pricing")
    def queryset(self, request):
        return super(OrderAdmin, self).queryset(request).select_related('plan', 'pricing', 'user')


class InvoiceAdmin(admin.ModelAdmin):
    search_fields = ('full_number',  'buyer_tax_number', 'user__username', 'user__email')
    list_filter = ('type', )
    list_display = ('full_number', "issued", "total_net", "currency", 'user', "tax", "buyer_name", "buyer_city", "buyer_tax_number")
    list_select_related = True

class UserPlanAdmin(admin.ModelAdmin):
    list_filter = ('active', 'expire')
    search_fields = ('user__username', 'user__email')
    list_display = ('user', 'plan', 'expire', 'active')
    list_select_related = True


admin.site.register(Quota, QuotaAdmin)
admin.site.register(Plan, PlanAdmin)
admin.site.register(UserPlan, UserPlanAdmin)
admin.site.register(Pricing)
admin.site.register(Order, OrderAdmin)
admin.site.register(BillingInfo, BillingInfoAdmin)
admin.site.register(Invoice, InvoiceAdmin)


