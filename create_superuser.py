# create_superuser.py
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'rs1500_backend.settings')
django.setup()

from django.contrib.auth.models import User

if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'password')
    print("Superuser created!")
else:
    print("Superuser already exists.")
