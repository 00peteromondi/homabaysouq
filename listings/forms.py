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

        def clean_image(self):
            image = self.cleaned_data.get('image')
            if image:
                # Cloudinary handles file validation, but you can add custom validation
                if hasattr(image, 'size') and image.size > 10 * 1024 * 1024:  # 10MB limit
                    raise forms.ValidationError("Image file too large ( > 10MB )")
            return image

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
    first_name = forms.CharField(max_length=30,
        help_text="Your first name"

    )
    last_name = forms.CharField(max_length=30,
        help_text="Your last name"
    )
    email = forms.EmailField(
        help_text="Your email address"
    )
    city = forms.CharField(max_length=50,
        help_text="Your city"
    )
    postal_code = forms.CharField(max_length=20,
        help_text="Your postal code"
    )

class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ['rating', 'comment']
        widgets = {
            'comment': forms.Textarea(attrs={'rows': 4}),
        }