from django.urls import path
from .views import (
    TeacherReviewQueueView,
    TeacherReviewOverrideView,
    AdminReviewQueueView,
    AdminReviewOverrideView,
    AdminAnalyticsView,
)

urlpatterns = [
    path("teacher/review-queue", TeacherReviewQueueView.as_view(), name="teacher-review-queue"),
    path("teacher/review/<int:result_id>", TeacherReviewOverrideView.as_view(), name="teacher-review-override"),
    path("admin/review-queue", AdminReviewQueueView.as_view(), name="admin-review-queue"),
    path("admin/review/<int:result_id>", AdminReviewOverrideView.as_view(), name="admin-review-override"),
    path("admin/analytics", AdminAnalyticsView.as_view(), name="admin-analytics"),
]
