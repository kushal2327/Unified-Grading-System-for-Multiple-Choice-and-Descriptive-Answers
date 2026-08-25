import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
import sys
sys.path.insert(0, '.')
import django
django.setup()

from django.db import connection
cursor = connection.cursor()
cursor.execute("SELECT * FROM users;")
rows = cursor.fetchall()
print('Users:', rows)