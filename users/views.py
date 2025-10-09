from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import PasswordChangeView
from django.views.generic import DetailView, UpdateView
from django.urls import reverse_lazy
from django.contrib import messages
from django import forms
from .models import User
from .forms import CustomUserCreationForm, CustomUserChangeForm
from listings.models import Listing
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404
from django.db import models

def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            
            # Fix: Explicitly set the backend and then login
            user.backend = 'django.contrib.auth.backends.ModelBackend'
            login(request, user)
            
            messages.success(request, 'Registration successful. Welcome!')
            return redirect('home')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = CustomUserCreationForm()
    
    # Check if there are social account tokens in session (for social registration)
    social_account = None
    if request.session.get('socialaccount_sociallogin'):
        social_account = request.session['socialaccount_sociallogin']
    
    return render(request, 'users/register.html', {
        'form': form,
        'social_account': social_account
    })

class ProfileDetailView(DetailView):
    model = User
    template_name = 'users/profile.html'
    context_object_name = 'profile_user'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile_user = self.object
        user = self.request.user

        # Listings by this user (paginated)
        listings_qs = Listing.objects.filter(seller=profile_user, is_sold=False).order_by('-date_created')
        paginator = Paginator(listings_qs, 8)
        page_number = self.request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        context['page_obj'] = page_obj

        # Saved listings (only for profile owner)
        saved_listings = None
        if user.is_authenticated and user == profile_user:
            saved_listings = Listing.objects.filter(favorites__user=user).order_by('-date_created')
        context['saved_listings'] = saved_listings

        # Listing count
        context['listing_count'] = listings_qs.count()

        # Saved count (only for profile owner)
        context['saved_count'] = saved_listings.count() if saved_listings is not None else 0

        # Rating average (you'll need to implement reviews for this to work)
        context['rating_average'] = 4.5  # Placeholder - implement your review system

        # Member since
        from django.utils import timezone
        from django.utils.timesince import timesince
        context['member_since'] = profile_user.date_joined.strftime("%B %Y")

        return context

class ProfileUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = User
    form_class = CustomUserChangeForm
    template_name = 'users/profile_edit.html'
    
    def get_success_url(self):
        return reverse_lazy('profile', kwargs={'pk': self.object.pk})

    def test_func(self):
        return self.request.user == self.get_object()
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Set initial values for the form
        form.fields['first_name'].initial = self.object.first_name
        form.fields['last_name'].initial = self.object.last_name
        form.fields['username'].initial = self.object.username
        form.fields['email'].initial = self.object.email
        form.fields['phone_number'].initial = self.object.phone_number
        form.fields['bio'].initial = self.object.bio
        form.fields['show_contact_info'].initial = self.object.show_contact_info
        
        return form
    
    def form_valid(self, form):
        # Handle profile picture upload
        if 'profile_picture' in self.request.FILES:
            form.instance.profile_picture = self.request.FILES['profile_picture']
        
        messages.success(self.request, 'Profile updated successfully!')
        return super().form_valid(form)
    
    def form_invalid(self, form):
        messages.error(self.request, 'Please correct the errors below.')
        return super().form_invalid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = self.get_form()
        return context

class CustomPasswordChangeView(LoginRequiredMixin, PasswordChangeView):
    template_name = 'users/password_change.html'
    success_url = reverse_lazy('password_change_done')
    
    def form_valid(self, form):
        messages.success(self.request, 'Your password has been changed successfully!')
        return super().form_valid(form)
