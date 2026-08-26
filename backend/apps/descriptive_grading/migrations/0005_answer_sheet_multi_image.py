from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("descriptive_grading", "0004_descriptiveresult_ground_truth_marks"),
    ]

    operations = [
        # 1. Add a new JSON column
        migrations.AddField(
            model_name="descriptiveresult",
            name="answer_sheets",
            field=models.JSONField(default=list, blank=True),
        ),
        # 2. Copy data: convert old string path(s) to a JSON list
        migrations.RunSQL(
            sql=(
                "UPDATE descriptive_results "
                "SET answer_sheets = "
                "  CASE WHEN answer_sheet IS NULL OR answer_sheet = '' THEN '[]'::json "
                "       ELSE json_build_array(answer_sheet) "
                "  END;"
            ),
            reverse_sql=(
                "UPDATE descriptive_results "
                "SET answer_sheet = "
                "  CASE WHEN answer_sheets IS NOT NULL AND json_array_length(answer_sheets) > 0 "
                "       THEN answer_sheets->>0 "
                "       ELSE NULL "
                "  END;"
            ),
        ),
        # 3. Remove old column
        migrations.RemoveField(
            model_name="descriptiveresult",
            name="answer_sheet",
        ),
        # 4. Rename new column to answer_sheet
        migrations.RenameField(
            model_name="descriptiveresult",
            old_name="answer_sheets",
            new_name="answer_sheet",
        ),
    ]
