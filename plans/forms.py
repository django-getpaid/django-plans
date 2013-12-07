from django import forms
from django.core.exceptions import ValidationError
from django.db.models import get_model
from django.forms.widgets import HiddenInput

PlanPricing = get_model('plans', 'PlanPricing')
BillingInfo = get_model('plans', 'BillingInfo')
Order = get_model('plans', 'Order')


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

    def clean(self):
        cleaned_data = super(BillingInfoForm, self).clean()

        try:
            cleaned_data['tax_number'] = BillingInfo.clean_tax_number(cleaned_data['tax_number'], cleaned_data.get('country', None))
        except ValidationError, e:
            self._errors['tax_number'] = e.messages

        return cleaned_data

class BillingInfoWithoutShippingForm(BillingInfoForm):
    class Meta:
        model = BillingInfo
        exclude = ('user', 'shipping_name', 'shipping_street', 'shipping_zipcode', 'shipping_city')
