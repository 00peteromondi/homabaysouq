# listings/forms.py
from django import forms
from .models import Listing, Category
from .models import Payment

class ListingForm(forms.ModelForm):
    class Meta:
        model = Listing
        fields = ['title', 'description', 'price', 'category', 'location', 'image', 'condition', 'delivery_option', 'stock']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Describe your item in detail...'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'location': forms.Select(attrs={'class': 'form-select'}),
            'condition': forms.Select(attrs={'class': 'form-select'}),
            'delivery_option': forms.Select(attrs={'class': 'form-select'}),
        }

# In listings/forms.py
from django import forms
from .models import Review

class CheckoutForm(forms.Form):
    shipping_address = forms.CharField(
        max_length=200,
        widget=forms.Textarea(attrs={'rows': 3}),
        help_text="Where should we deliver your items?"
    )
    phone_number = forms.CharField(
        max_length=15,
        help_text="Your phone number for delivery updates"
    )
    payment_method = forms.ChoiceField(
        choices=Payment.PAYMENT_METHODS,
        initial='mpesa',
        widget=forms.RadioSelect
    )

class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ['rating', 'comment']
        widgets = {
            'comment': forms.Textarea(attrs={'rows': 4}),
        }