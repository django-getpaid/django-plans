from django.contrib import admin
from django.db.models import get_model
from modeltranslation.admin import TranslationAdmin
from plans.admin import UserLinkMixin, PlanAdmin, QuotaAdmin

Plan = get_model('plans', 'Plan')
Quota = get_model('plans', 'Quota')
Pricing = get_model('plans', 'Pricing')

# Admin translation for django-plans

class TranslatedPlanAdmin(PlanAdmin, TranslationAdmin):
    pass

admin.site.unregister(Plan)
admin.site.register(Plan, TranslatedPlanAdmin)


class TranslatedPricingAdmin(TranslationAdmin):
    pass

admin.site.unregister(Pricing)
admin.site.register(Pricing, TranslatedPricingAdmin)


class TranslatedQuotaAdmin(QuotaAdmin, TranslationAdmin):
    pass

admin.site.unregister(Quota)
admin.site.register(Quota, TranslatedQuotaAdmin)

