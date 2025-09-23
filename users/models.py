from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30)
    phone_number = models.CharField(max_length=15, blank=True, null=True, unique=True)
    location = models.CharField(max_length=100, help_text="Your specific area in Homabay, e.g., Ndhiva, Rodi Kopany")
    bio = models.TextField(max_length=500, blank=True)
    profile_picture = models.ImageField(upload_to='profile_pics/', default='default_profile_pic.jpg')
    is_verified = models.BooleanField(default=False)
    show_contact_info = models.BooleanField(default=True, help_text="Show my contact information to other users")
    date_joined = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.username