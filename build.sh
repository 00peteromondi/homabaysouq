
#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt

# Apply database migrations
python manage.py migrate

# Create social applications
python manage.py setup_social_apps

# Create static directories
mkdir -p media/listing_images
mkdir -p media/profile_pics
mkdir -p media/blog_images

mkdir -p static/images
mkdir -p static/css
mkdir -p static/js
mkdir -p templates/socialaccount
mkdir -p templates/account


# Collect static files
python manage.py collectstatic --no-input
