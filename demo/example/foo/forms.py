from django.forms import HiddenInput, ModelForm

from .models import Foo
from .validators import max_foos_validator


class FooForm(ModelForm):
    class Meta:
        model = Foo
        fields = '__all__'
        widgets = {
            'user': HiddenInput,
        }

    def clean(self):
        cleaned_data = super(FooForm, self).clean()
        max_foos_validator(cleaned_data['user'], add=1)
        return cleaned_data
