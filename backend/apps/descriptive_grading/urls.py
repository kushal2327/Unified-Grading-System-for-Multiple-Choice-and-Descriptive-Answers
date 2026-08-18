from django.urls import path
from .views import (
    TeacherMaterialUploadView,
    TeacherMaterialListView,
    ExamCreateView,
    ExamListView,
    StudentSubmitAnswerView,
    StudentResultsView,
    TeacherExamResultsView,
    ExamQuestionsView,
    MaterialChunksView,
)

urlpatterns = [
    path("student/submit-answer", StudentSubmitAnswerView.as_view(), name="student-submit-answer"),
    path("student/results/<int:exam_id>", StudentResultsView.as_view(), name="student-results"),
    path("student/exams/<int:exam_id>", ExamQuestionsView.as_view(), name="student-exam-questions"),
    path("teacher/upload-material", TeacherMaterialUploadView.as_view(), name="teacher-upload-material"),
    path("teacher/materials", TeacherMaterialListView.as_view(), name="teacher-materials"),
    path("teacher/create-exam", ExamCreateView.as_view(), name="teacher-create-exam"),
    path("teacher/exams", ExamListView.as_view(), name="teacher-exams"),
    path("teacher/results/<int:exam_id>", TeacherExamResultsView.as_view(), name="teacher-results"),
    path("teacher/materials/<int:material_id>/chunks", MaterialChunksView.as_view(), name="teacher-material-chunks"),
]