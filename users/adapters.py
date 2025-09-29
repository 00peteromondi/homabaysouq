from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.socialaccount.models import SocialApp
from django.contrib.sites.models import Site
from django.http import Http404

class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    def get_app(self, request, provider, client_id=None):
        """
        Override to handle multiple social apps gracefully
        """
        try:
            # First, try the default behavior
            return super().get_app(request, provider, client_id)
        except SocialApp.MultipleObjectsReturned:
            # If multiple apps found, get the current site and return the first one
            site = Site.objects.get_current(request)
            apps = SocialApp.objects.filter(
                provider=provider, 
                sites=site
            )
            if client_id:
                apps = apps.filter(client_id=client_id)
            
            if apps.exists():
                return apps.first()
            raise Http404("No social app found")