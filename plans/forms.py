from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.forms.widgets import HiddenInput
from django.utils.translation import ugettext

from .models import PlanPricing, BillingInfo
from plans.models import Order


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def get_country_code(request):
    if getattr(settings, 'PLANS_GET_COUNTRY_FROM_IP', False):
        try:
            from geolite2 import geolite2
            reader = geolite2.reader()
            ip_address = get_client_ip(request)
            ip_info = reader.get(ip_address)
        except ModuleNotFoundError:
            ip_info = None

        if ip_info and 'country' in ip_info:
            country_code = ip_info['country']['iso_code']
            return country_code
    return getattr(settings, 'PLANS_DEFAULT_COUNTRY', None)


class OrderForm(forms.Form):
    plan_pricing = forms.ModelChoiceField(queryset=PlanPricing.objects.all(), widget=HiddenInput, required=True)


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
        exclude = ('user',)

    def __init__(self, *args, request=None, **kwargs):
        ret_val = super().__init__(*args, **kwargs)
        if not self.instance.country:
            self.fields['country'].initial = get_country_code(request)
        return ret_val

    def clean(self):
        cleaned_data = super(BillingInfoForm, self).clean()

        try:
            cleaned_data['tax_number'] = BillingInfo.clean_tax_number(cleaned_data['tax_number'],
                                                                      cleaned_data.get('country', None))
        except ValidationError as e:
            self._errors['tax_number'] = e.messages

        return cleaned_data


class BillingInfoWithoutShippingForm(BillingInfoForm):
    class Meta:
        model = BillingInfo
        exclude = ('user', 'shipping_name', 'shipping_street', 'shipping_zipcode', 'shipping_city')


class FakePaymentsForm(forms.Form):
    status = forms.ChoiceField(choices=Order.STATUS, required=True, label=ugettext('Change order status to'))
