from django.contrib import admin
from modeltranslation.admin import TranslationAdmin

from plans.admin import PlanAdmin, QuotaAdmin
from plans.base.models import AbstractPlan, AbstractPricing, AbstractQuota

Plan = AbstractPlan.get_concrete_model()
Quota = AbstractQuota.get_concrete_model()
Pricing = AbstractPricing.get_concrete_model()

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
