from django.conf import settings
from django.db import models

from apps.descriptive_grading.models import DescriptiveResult


class ManualReviewQueue(models.Model):
    REASON_CHOICES = (
        ("low_ocr_confidence", "Low OCR Confidence"),
        ("low_similarity", "Low Similarity"),
        ("llm_invalid", "LLM Invalid Response"),
    )
    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("reviewed", "Reviewed"),
    )

    result = models.ForeignKey(DescriptiveResult, on_delete=models.CASCADE, related_name="review_entries")
    reason = models.CharField(max_length=30, choices=REASON_CHOICES)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_items",
        limit_choices_to={"role": "admin"},
    )
    override_marks = models.FloatField(blank=True, null=True)
    override_feedback = models.TextField(blank=True, null=True)
    reviewed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = "manual_review_queue"

    def __str__(self):
        return f"Review {self.id} ({self.reason}) - {self.status}"
