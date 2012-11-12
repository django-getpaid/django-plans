from django.forms import ModelForm, HiddenInput
from example.foo.models import Foo

class FooForm(ModelForm):
    class Meta:
        model = Foo
        widgets = {
            'user' : HiddenInput,
        }