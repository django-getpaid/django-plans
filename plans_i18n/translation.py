from django.db.models import get_model
from modeltranslation.translator import translator, TranslationOptions
from plans.models import Plan, Pricing, Quota

Plan = get_model('plans', 'Plan')
Pricing = get_model('plans', 'Pricing')
Quota = get_model('plans', 'Quota')


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