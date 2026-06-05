import os
import sys
import django
from django.test import Client

# Asegurar que el directorio base del proyecto está en sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings.development')
django.setup()

c = Client()
resp = c.get('/api/v1/pagos/')
print('STATUS:', resp.status_code)
print(resp.content.decode('utf-8')[:2000])
