from django.urls import path
from .views import (
    TeacherMaterialUploadView,
    TeacherMaterialListView,
    ExamCreateView,
    ExamListView,
    ExamUpdateView,
    StudentSubmitAnswerView,
    StudentResultsView,
    StudentAnswerDeleteView,
    TeacherExamResultsView,
    TeacherExamSubmissionsView,
    ExamQuestionsView,
    MaterialChunksView,
    ExamLookupByCodeView,
    VisionModelStatusView,
)

urlpatterns = [
    path("student/submit-answer", StudentSubmitAnswerView.as_view(), name="student-submit-answer"),
    path("student/results/<str:exam_id>", StudentResultsView.as_view(), name="student-results"),
    path("student/result/<int:result_id>", StudentAnswerDeleteView.as_view(), name="student-answer-delete"),
    path("student/exams/lookup", ExamLookupByCodeView.as_view(), name="student-exam-lookup"),
    path("student/exams/<int:exam_id>", ExamQuestionsView.as_view(), name="student-exam-questions"),
    path("teacher/upload-material", TeacherMaterialUploadView.as_view(), name="teacher-upload-material"),
    path("teacher/materials", TeacherMaterialListView.as_view(), name="teacher-materials"),
    path("teacher/create-exam", ExamCreateView.as_view(), name="teacher-create-exam"),
    path("teacher/exams", ExamListView.as_view(), name="teacher-exams"),
    path("teacher/exams/<int:pk>", ExamUpdateView.as_view(), name="teacher-exam-update"),
    path("teacher/results/<int:exam_id>", TeacherExamResultsView.as_view(), name="teacher-results"),
    path("teacher/submissions/<int:exam_id>", TeacherExamSubmissionsView.as_view(), name="teacher-submissions"),
    path("teacher/materials/<int:material_id>/chunks", MaterialChunksView.as_view(), name="teacher-material-chunks"),
    path("teacher/vision-status", VisionModelStatusView.as_view(), name="teacher-vision-status"),
]