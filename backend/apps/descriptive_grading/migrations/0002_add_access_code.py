import datetime
from django.db import migrations, models


def forwards(apps, schema_editor):
    Exam = apps.get_model('descriptive_grading', 'Exam')
    with connection.cursor() as cursor:
        # Add access_code column
        cursor.execute(
            "ALTER TABLE exams ADD COLUMN access_code varchar(4) DEFAULT ''"
        )
        # Add valid_until column
        cursor.execute(
            "ALTER TABLE exams ADD COLUMN valid_until timestamp with time zone DEFAULT now() + interval '7 days'"
        )
        # Assign unique 4-digit codes to existing exams
        for i, exam in enumerate(Exam.objects.all()):
            code = f"{i + 1:04d}"
            exam.access_code = code
            exam.save(update_fields=['access_code'])


def backwards(apps, schema_editor):
    with connection.cursor() as cursor:
        cursor.execute("ALTER TABLE exams DROP COLUMN IF EXISTS access_code")
        cursor.execute("ALTER TABLE exams DROP COLUMN IF EXISTS valid_until")


from django.db import connection


class Migration(migrations.Migration):

    dependencies = [
        ('descriptive_grading', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
