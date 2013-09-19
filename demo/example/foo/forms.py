from django.forms import ModelForm, HiddenInput
from .models import Foo
from .validators import max_foos_validator


class FooForm(ModelForm):
    class Meta:
        model = Foo
        widgets = {
            'user' : HiddenInput,
        }

    def clean(self):
        cleaned_data = super(FooForm, self).clean()
        max_foos_validator(cleaned_data['user'], add=1)
        return cleaned_data