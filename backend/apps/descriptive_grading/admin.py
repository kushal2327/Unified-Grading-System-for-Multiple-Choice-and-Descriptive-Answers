from django.contrib import admin
from .models import Exam, Question, TeacherMaterial, Submission, DescriptiveResult


@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "subject", "teacher", "created_at")
    list_filter = ("subject",)


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("id", "exam", "total_marks")


@admin.register(TeacherMaterial)
class TeacherMaterialAdmin(admin.ModelAdmin):
    list_display = ("id", "filename", "subject", "teacher", "chunked", "uploaded_at")
    list_filter = ("chunked", "subject")


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ("id", "student", "exam", "status", "submitted_at")
    list_filter = ("status",)


@admin.register(DescriptiveResult)
class DescriptiveResultAdmin(admin.ModelAdmin):
    list_display = (
        "id", "submission", "question", "ocr_confidence",
        "similarity_score", "marks_awarded", "total_marks", "flagged",
    )
    list_filter = ("flagged",)
