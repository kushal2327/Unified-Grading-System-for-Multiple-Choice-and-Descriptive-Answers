from django.db.models import Avg, Count, Q
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.authentication.permissions import IsTeacher, IsAdminRole
from apps.descriptive_grading.models import DescriptiveResult, Submission

from .models import ManualReviewQueue
from .serializers import ManualReviewQueueSerializer, AdminOverrideSerializer


class TeacherReviewQueueView(generics.ListAPIView):
    """
    GET /api/teacher/review-queue
    Flagged answers pending review, restricted to the current
    teacher's own exams.
    """
    permission_classes = [permissions.IsAuthenticated, IsTeacher]
    serializer_class = ManualReviewQueueSerializer

    def get_queryset(self):
        return ManualReviewQueue.objects.filter(
            result__question__exam__teacher=self.request.user,
            status="pending",
        ).select_related("result", "result__submission", "result__question").order_by("-id")


class AdminReviewQueueView(generics.ListAPIView):
    """GET /api/admin/review-queue -> all flagged answers across all exams"""
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]
    serializer_class = ManualReviewQueueSerializer

    def get_queryset(self):
        queryset = ManualReviewQueue.objects.select_related(
            "result", "result__submission", "result__question"
        ).order_by("-id")
        status_filter = self.request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        return queryset


class AdminReviewOverrideView(APIView):
    """
    POST /api/admin/review/{result_id}
    Body: {override_marks, override_feedback}

    Applies a manual override to the DescriptiveResult, updates the
    linked ManualReviewQueue entry to "reviewed", and marks the
    submission as graded.
    """
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def post(self, request, result_id):
        try:
            result = DescriptiveResult.objects.get(id=result_id)
        except DescriptiveResult.DoesNotExist:
            return Response({"detail": "Result not found."}, status=status.HTTP_404_NOT_FOUND)

        review_entry = ManualReviewQueue.objects.filter(result=result, status="pending").order_by("-id").first()
        if review_entry is None:
            return Response(
                {"detail": "This result has no pending manual review entry."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = AdminOverrideSerializer(data=request.data, context={"result": result})
        serializer.is_valid(raise_exception=True)

        override_marks = serializer.validated_data["override_marks"]
        override_feedback = serializer.validated_data["override_feedback"]

        # Apply the override onto the actual result the student/teacher see
        result.marks_awarded = override_marks
        result.feedback = override_feedback
        result.flagged = False
        result.save(update_fields=["marks_awarded", "feedback", "flagged"])

        review_entry.status = "reviewed"
        review_entry.reviewed_by = request.user
        review_entry.override_marks = override_marks
        review_entry.override_feedback = override_feedback
        review_entry.reviewed_at = timezone.now()
        review_entry.save(update_fields=[
            "status", "reviewed_by", "override_marks", "override_feedback", "reviewed_at"
        ])

        # If every result for this submission is now unflagged, mark it graded.
        submission = result.submission
        if not submission.results.filter(flagged=True).exists():
            submission.status = "graded"
            submission.save(update_fields=["status"])

        return Response(ManualReviewQueueSerializer(review_entry).data, status=status.HTTP_200_OK)


class AdminAnalyticsView(APIView):
    """
    GET /api/admin/analytics
    Total submissions, average scores, flag rate, OCR confidence averages.
    """
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def get(self, request):
        total_submissions = Submission.objects.count()
        total_results = DescriptiveResult.objects.count()
        flagged_count = DescriptiveResult.objects.filter(flagged=True).count()

        avg_marks_pct = None
        graded_results = DescriptiveResult.objects.filter(marks_awarded__isnull=False, total_marks__gt=0)
        if graded_results.exists():
            # Average (marks_awarded / total_marks) across results, as a percentage.
            pct_values = [
                (r.marks_awarded / r.total_marks) * 100
                for r in graded_results
            ]
            avg_marks_pct = sum(pct_values) / len(pct_values)

        avg_ocr_confidence = DescriptiveResult.objects.filter(
            ocr_confidence__isnull=False
        ).aggregate(avg=Avg("ocr_confidence"))["avg"]

        flag_reason_breakdown = list(
            ManualReviewQueue.objects.values("reason").annotate(count=Count("id")).order_by("-count")
        )

        return Response({
            "total_submissions": total_submissions,
            "total_results": total_results,
            "flagged_count": flagged_count,
            "flag_rate_percent": round((flagged_count / total_results * 100), 2) if total_results else 0,
            "average_score_percent": round(avg_marks_pct, 2) if avg_marks_pct is not None else None,
            "average_ocr_confidence": round(avg_ocr_confidence, 2) if avg_ocr_confidence is not None else None,
            "flag_reason_breakdown": flag_reason_breakdown,
        })
