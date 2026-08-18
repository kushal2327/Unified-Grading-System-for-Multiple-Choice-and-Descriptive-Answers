from django.contrib import admin
from .models import ManualReviewQueue


@admin.register(ManualReviewQueue)
class ManualReviewQueueAdmin(admin.ModelAdmin):
    list_display = ("id", "result", "reason", "status", "reviewed_by", "reviewed_at")
    list_filter = ("reason", "status")
