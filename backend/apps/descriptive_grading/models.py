from django.conf import settings
from django.db import models


class Exam(models.Model):
    title = models.CharField(max_length=255)
    subject = models.CharField(max_length=255)
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="exams",
        limit_choices_to={"role": "teacher"},
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "exams"

    def __str__(self):
        return self.title


class Question(models.Model):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="questions")
    question_text = models.TextField()
    total_marks = models.PositiveIntegerField()
    rubric = models.TextField(help_text='e.g. "5 key points, 2 marks each, total 10"')

    class Meta:
        db_table = "questions"

    def __str__(self):
        return f"Q{self.id} - {self.exam.title}"


class TeacherMaterial(models.Model):
    subject = models.CharField(max_length=255)
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="materials",
        limit_choices_to={"role": "teacher"},
    )
    filename = models.CharField(max_length=255)
    file_path = models.FileField(upload_to="teacher_materials/")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    chunked = models.BooleanField(default=False)

    class Meta:
        db_table = "teacher_materials"

    def __str__(self):
        return self.filename


class Submission(models.Model):
    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("graded", "Graded"),
        ("flagged", "Flagged"),
    )

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="submissions",
        limit_choices_to={"role": "student"},
    )
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="submissions")
    submitted_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")

    class Meta:
        db_table = "submissions"

    def __str__(self):
        return f"Submission {self.id} - {self.student.name}"


class DescriptiveResult(models.Model):
    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name="results")
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="results")

    ocr_raw_text = models.TextField(blank=True, null=True)
    ocr_cleaned_text = models.TextField(blank=True, null=True)
    ocr_confidence = models.FloatField(blank=True, null=True)

    similarity_score = models.FloatField(blank=True, null=True)
    retrieved_chunks = models.JSONField(blank=True, null=True, default=list)

    marks_awarded = models.FloatField(blank=True, null=True)
    total_marks = models.FloatField()

    feedback = models.TextField(blank=True, null=True)
    justification = models.JSONField(blank=True, null=True, default=dict)

    flagged = models.BooleanField(default=False)
    flag_reason = models.CharField(max_length=50, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "descriptive_results"

    def __str__(self):
        return f"Result {self.id} (submission {self.submission_id})"
