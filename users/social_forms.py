from django import forms
from allauth.socialaccount.forms import SignupForm
from .models import User

class CustomSocialSignupForm(SignupForm):
    first_name = forms.CharField(max_length=30, label='First Name')
    last_name = forms.CharField(max_length=30, label='Last Name')
    phone_number = forms.CharField(max_length=15, required=False, label='Phone Number')
    location = forms.CharField(max_length=100, required=True, label='Location', 
                              help_text="Your specific area in Homabay, e.g., Ndhiwa, Rodi Kopany")
    # Add any additional fields you need for your signup form
    

    def save(self, request):
        user = super().save(request)
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.phone_number = self.cleaned_data['phone_number']
        user.location = self.cleaned_data['location']
        user.save()
        return user