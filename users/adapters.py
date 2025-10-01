from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.socialaccount.models import SocialApp
from django.contrib.sites.models import Site
from django.http import Http404
from django.conf import settings
from django.contrib import messages
import os

class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    def get_app(self, request, provider, client_id=None):
        """
        Override to handle social apps gracefully
        """
        try:
            # First, try the default behavior
            return super().get_app(request, provider, client_id)
        except SocialApp.DoesNotExist:
            # If no app exists, try to create one on the fly
            self.create_social_app_from_env(provider)
            # Try again after creation
            return super().get_app(request, provider, client_id)
        except SocialApp.MultipleObjectsReturned:
            # If multiple apps found, get the current site and return the first one
            site = Site.objects.get_current()
            apps = SocialApp.objects.filter(
                provider=provider, 
                sites=site
            )
            if client_id:
                apps = apps.filter(client_id=client_id)
            
            if apps.exists():
                return apps.first()
            raise Http404(f"No social app found for {provider}")

    def create_social_app_from_env(self, provider):
        """Create a social app from environment variables"""
        site = Site.objects.get_current()
        
        if provider == 'google':
            client_id = os.environ.get('GOOGLE_OAUTH_CLIENT_ID')
            secret = os.environ.get('GOOGLE_OAUTH_CLIENT_SECRET')
            name = 'Google'
        elif provider == 'facebook':
            client_id = os.environ.get('FACEBOOK_OAUTH_CLIENT_ID')
            secret = os.environ.get('FACEBOOK_OAUTH_CLIENT_SECRET')
            name = 'Facebook'
        else:
            raise Http404(f"Provider {provider} not supported")
        
        if not client_id or not secret:
            raise Http404(f"No OAuth credentials found for {provider}. Please set {provider.upper()}_OAUTH_CLIENT_ID and {provider.upper()}_OAUTH_CLIENT_SECRET environment variables.")
        
        # Create the social app
        app, created = SocialApp.objects.get_or_create(
            provider=provider,
            defaults={
                'name': name,
                'client_id': client_id,
                'secret': secret,
            }
        )
        app.sites.add(site)
        
        return app

    def pre_social_login(self, request, sociallogin):
        """
        This is called before the social login is complete.
        We can use this to handle the user creation process.
        """
        user = sociallogin.user
        if user.id:
            # User already exists, just log them in
            return
        # New user - we'll handle this in save_user

    def save_user(self, request, sociallogin, form=None):
        """
        Saves a newly signed up social login.
        """
        print(f"🔍 Social login data: {sociallogin.account.extra_data}")
        
        user = super().save_user(request, sociallogin, form)
        
        # Extract data from social account
        extra_data = sociallogin.account.extra_data
        print(f"🔍 Extra data: {extra_data}")
        
        # Update user fields with social data
        if extra_data:
            # For Google
            if 'given_name' in extra_data and not user.first_name:
                user.first_name = extra_data.get('given_name', '')
            if 'family_name' in extra_data and not user.last_name:
                user.last_name = extra_data.get('family_name', '')
            if 'name' in extra_data and not user.first_name:
                # Try to split full name
                name_parts = extra_data.get('name', '').split(' ', 1)
                if len(name_parts) > 0 and not user.first_name:
                    user.first_name = name_parts[0]
                if len(name_parts) > 1 and not user.last_name:
                    user.last_name = name_parts[1]
            if 'email' in extra_data and not user.email:
                user.email = extra_data.get('email', '')
        
        print(f"🔍 Saving user: {user.username}, {user.email}, {user.first_name} {user.last_name}")
        user.save()
        return user

    def get_connect_redirect_url(self, request, socialaccount):
        """
        Returns the default URL to redirect to after successfully
        connecting a social account.
        """
        return '/'

    def authentication_error(self, request, provider_id, error=None, exception=None, extra_context=None):
        """
        Handle authentication errors gracefully.
        """
        messages.error(request, f"Authentication failed with {provider_id}. Please try again.")
        return super().authentication_error(request, provider_id, error, exception, extra_context)