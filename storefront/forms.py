from django import forms
from .models import Store
from listings.forms import ListingForm
from .mpesa import MpesaGateway


class UpgradeForm(forms.Form):
    phone_number = forms.CharField(max_length=32, required=True, label='Phone Number')

    def clean_phone_number(self):
        val = self.cleaned_data.get('phone_number')
        try:
            # Use the gateway normalizer to validate and canonicalize
            norm = MpesaGateway._normalize_phone(None, val)
            return norm
        except Exception as e:
            raise forms.ValidationError(str(e))


class StoreForm(forms.ModelForm):
    class Meta:
        model = Store
        fields = ['name', 'slug', 'description', 'is_premium']


# Reuse ListingForm for creating/editing storefront "products" (listings)
class ProductForm(ListingForm):
    pass
