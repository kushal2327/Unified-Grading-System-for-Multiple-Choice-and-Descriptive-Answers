from django.db.models import Avg, Count, Q
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.authentication.permissions import IsTeacher, IsAdminRole
from apps.descriptive_grading.models import DescriptiveResult, Exam, Submission

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


def _apply_override(request, result):
    """Shared logic for overriding a flagged result (used by admin + teacher)."""
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

        return _apply_override(request, result)


class TeacherReviewOverrideView(APIView):
    """
    POST /api/teacher/review/{result_id}
    Body: {override_marks, override_feedback}

    Lets a teacher review flagged answers from their own exams directly.
    Behaviour is identical to the admin override, but scoped so a teacher
    can only touch results belonging to exams they created.
    """
    permission_classes = [permissions.IsAuthenticated, IsTeacher]

    def post(self, request, result_id):
        try:
            result = DescriptiveResult.objects.get(id=result_id)
        except DescriptiveResult.DoesNotExist:
            return Response({"detail": "Result not found."}, status=status.HTTP_404_NOT_FOUND)

        if result.submission.exam.teacher_id != request.user.id:
            return Response(
                {"detail": "This result does not belong to any of your exams."},
                status=status.HTTP_403_FORBIDDEN,
            )

        return _apply_override(request, result)


class AdminAnalyticsView(APIView):
    """
    GET /api/admin/analytics
    Totals + distributions (score buckets, OCR confidence buckets,
    submission statuses, flag reasons) and per-exam breakdowns so the
    admin analytics page can draw charts.
    """
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    SCORE_BUCKETS = [
        {"label": "0-20%", "count": 0},
        {"label": "21-40%", "count": 0},
        {"label": "41-60%", "count": 0},
        {"label": "61-80%", "count": 0},
        {"label": "81-100%", "count": 0},
    ]
    OCR_BUCKETS = [
        {"label": "<50%", "count": 0},
        {"label": "50-60%", "count": 0},
        {"label": "60-70%", "count": 0},
        {"label": "70-80%", "count": 0},
        {"label": "80-90%", "count": 0},
        {"label": "90-100%", "count": 0},
    ]

    def get(self, request):
        total_submissions = Submission.objects.count()
        total_results = DescriptiveResult.objects.count()
        flagged_count = DescriptiveResult.objects.filter(flagged=True).count()

        graded_results = list(
            DescriptiveResult.objects.filter(marks_awarded__isnull=False, total_marks__gt=0)
            .values_list("marks_awarded", "total_marks")
        )
        avg_marks_pct = None
        score_distribution = [dict(b) for b in self.SCORE_BUCKETS]
        if graded_results:
            pct_values = []
            for marks, total in graded_results:
                pct = (marks / total) * 100
                pct_values.append(pct)
                bucket_idx = 4 if pct >= 80 else int(pct // 20)
                score_distribution[bucket_idx]["count"] += 1
            avg_marks_pct = sum(pct_values) / len(pct_values)

        confidence_rows = list(
            DescriptiveResult.objects.filter(ocr_confidence__isnull=False)
            .values_list("ocr_confidence", flat=True)
        )
        ocr_distribution = [dict(b) for b in self.OCR_BUCKETS]
        for conf in confidence_rows:
            if conf < 50:
                idx = 0
            else:
                idx = min(5, 1 + int((conf - 50) // 10))
            ocr_distribution[idx]["count"] += 1

        avg_ocr_confidence = (
            round(sum(confidence_rows) / len(confidence_rows), 2) if confidence_rows else None
        )

        avg_similarity = DescriptiveResult.objects.filter(
            similarity_score__isnull=False
        ).aggregate(avg=Avg("similarity_score"))["avg"]

        submission_status_breakdown = list(
            Submission.objects.values("status").annotate(count=Count("id")).order_by("status")
        )

        flag_reason_breakdown = list(
            ManualReviewQueue.objects.values("reason").annotate(count=Count("id")).order_by("-count")
        )

        # Per-exam rollup: submissions via ORM annotation, result aggregates
        # grouped in Python (avg of per-result percentages).
        results_by_exam = {}
        for row in DescriptiveResult.objects.values("question__exam_id").annotate(
            n=Count("id"),
            flagged_n=Count("id", filter=Q(flagged=True)),
        ):
            results_by_exam[row["question__exam_id"]] = row

        pcts_by_exam = {}
        for marks, total, exam_id in DescriptiveResult.objects.filter(
            marks_awarded__isnull=False, total_marks__gt=0
        ).values_list("marks_awarded", "total_marks", "question__exam_id"):
            pcts_by_exam.setdefault(exam_id, []).append((marks / total) * 100)

        per_exam = []
        for exam in Exam.objects.annotate(num_submissions=Count("submissions", distinct=True)):
            agg = results_by_exam.get(exam.id, {})
            pcts = pcts_by_exam.get(exam.id, [])
            per_exam.append({
                "exam_id": exam.id,
                "title": exam.title,
                "subject": exam.subject,
                "num_submissions": exam.num_submissions,
                "num_results": agg.get("n", 0),
                "flagged_count": agg.get("flagged_n", 0),
                "avg_score_percent": round(sum(pcts) / len(pcts), 2) if pcts else None,
            })

        return Response({
            "total_submissions": total_submissions,
            "total_results": total_results,
            "flagged_count": flagged_count,
            "flag_rate_percent": round((flagged_count / total_results * 100), 2) if total_results else 0,
            "average_score_percent": round(avg_marks_pct, 2) if avg_marks_pct is not None else None,
            "average_ocr_confidence": avg_ocr_confidence,
            "average_similarity": round(avg_similarity, 3) if avg_similarity is not None else None,
            "score_distribution": score_distribution,
            "ocr_confidence_distribution": ocr_distribution,
            "submission_status_breakdown": submission_status_breakdown,
            "flag_reason_breakdown": flag_reason_breakdown,
            "per_exam": per_exam,
        })
