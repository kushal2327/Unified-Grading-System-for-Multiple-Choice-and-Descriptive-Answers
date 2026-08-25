import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
import django
django.setup()

from apps.authentication.serializers import EmailTokenObtainPairSerializer
from django.test import RequestFactory

factory = RequestFactory()
request = factory.post('/api/auth/login', {'email': 'test@example.com', 'password': 'testpass123'})
serializer = EmailTokenObtainPairSerializer(data={'email': 'test@example.com', 'password': 'testpass123'}, context={'request': request})
print('Is valid:', serializer.is_valid())
if serializer.is_valid():
    print('Data:', serializer.validated_data)
else:
    print('Errors:', serializer.errors)