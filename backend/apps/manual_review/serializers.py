from rest_framework import serializers

from .models import ManualReviewQueue
from apps.descriptive_grading.serializers import DescriptiveResultSerializer


class ManualReviewQueueSerializer(serializers.ModelSerializer):
    result = DescriptiveResultSerializer(read_only=True)
    reviewed_by_name = serializers.CharField(source="reviewed_by.name", read_only=True, default=None)

    class Meta:
        model = ManualReviewQueue
        fields = [
            "id", "result", "reason", "status",
            "reviewed_by", "reviewed_by_name",
            "override_marks", "override_feedback", "reviewed_at",
        ]
        read_only_fields = ["id", "result", "reason", "reviewed_by", "reviewed_by_name", "reviewed_at"]


class AdminOverrideSerializer(serializers.Serializer):
    """POST /api/admin/review/{result_id} body"""
    override_marks = serializers.FloatField(required=True)
    override_feedback = serializers.CharField(required=True, allow_blank=False)

    def validate_override_marks(self, value):
        result = self.context["result"]
        if value < 0 or value > result.total_marks:
            raise serializers.ValidationError(
                f"override_marks must be between 0 and {result.total_marks}"
            )
        return value
