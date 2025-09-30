from django.core.management.base import BaseCommand
from django.contrib.sites.models import Site
from allauth.socialaccount.models import SocialApp
from django.conf import settings

class Command(BaseCommand):
    help = 'Create social applications for OAuth providers'

    def handle(self, *args, **options):
        # Get the current site
        site = Site.objects.get_current()
        
        # Create Google SocialApp if it doesn't exist
        google_app, created = SocialApp.objects.get_or_create(
            provider='google',
            defaults={
                'name': 'Google',
                'client_id': getattr(settings, 'GOOGLE_OAUTH_CLIENT_ID', ''),
                'secret': getattr(settings, 'GOOGLE_OAUTH_CLIENT_SECRET', ''),
            }
        )
        if created:
            google_app.sites.add(site)
            self.stdout.write(self.style.SUCCESS('Google SocialApp created'))
        else:
            self.stdout.write(self.style.WARNING('Google SocialApp already exists'))

        # Create Facebook SocialApp if it doesn't exist
        facebook_app, created = SocialApp.objects.get_or_create(
            provider='facebook',
            defaults={
                'name': 'Facebook',
                'client_id': getattr(settings, 'FACEBOOK_OAUTH_CLIENT_ID', ''),
                'secret': getattr(settings, 'FACEBOOK_OAUTH_CLIENT_SECRET', ''),
            }
        )
        if created:
            facebook_app.sites.add(site)
            self.stdout.write(self.style.SUCCESS('Facebook SocialApp created'))
        else:
            self.stdout.write(self.style.WARNING('Facebook SocialApp already exists'))