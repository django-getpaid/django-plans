from django import forms
from django.core.exceptions import ValidationError
from models import PlanPricing, BillingInfo
from django.forms.widgets import HiddenInput
from plans.models import Order


class OrderForm(forms.Form):
    plan_pricing = forms.ModelChoiceField(queryset=PlanPricing.objects.all(), widget=HiddenInput, required = True)

class CreateOrderForm(forms.ModelForm):
    """
    This form is intentionally empty as all values for Order object creation need to be computed inside view

    Therefore, when implementing for example a rabat coupons, you can add some fields here
     and create "recalculate" button.
    """
    class Meta:
        model = Order
        fields = tuple()


class BillingInfoForm(forms.ModelForm):
    class Meta:
        model = BillingInfo
        exclude=('user',)

    def clean_tax_number(self):
        self.cleaned_data['tax_number'] = BillingInfo.clean_tax_number(self.cleaned_data['tax_number'], self.cleaned_data.get('country', None))
        return self.cleaned_data['tax_number']


class BillingInfoWithoutShippingForm(BillingInfoForm):
    class Meta:
        model = BillingInfo
        exclude = ('user', 'shipping_name', 'shipping_street', 'shipping_zipcode', 'shipping_city')
