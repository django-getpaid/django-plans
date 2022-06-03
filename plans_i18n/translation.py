from modeltranslation.translator import TranslationOptions, translator

from plans.base.models import AbstractPlan, AbstractPricing, AbstractQuota

Plan = AbstractPlan.get_concrete_model()
Pricing = AbstractPricing.get_concrete_model()
Quota = AbstractQuota.get_concrete_model()

# Translations for django-plans


class PlanTranslationOptions(TranslationOptions):
    fields = ('name', 'description', )


translator.register(Plan, PlanTranslationOptions)


class PricingTranslationOptions(TranslationOptions):
    fields = ('name',)


translator.register(Pricing, PricingTranslationOptions)


class QuotaTranslationOptions(TranslationOptions):
    fields = ('name', 'description', 'unit')


translator.register(Quota, QuotaTranslationOptions)
