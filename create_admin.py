import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fintech_core.settings')
django.setup()

from django.contrib.auth.models import User

if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@fintech.com', 'admin123')
    print("Superuser created.")
else:
    print("Superuser already exists.")
