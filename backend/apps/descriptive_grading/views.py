import logging

from rest_framework import generics, permissions, status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.authentication.permissions import IsTeacher, IsStudent
from .models import TeacherMaterial, Exam, Question, Submission, DescriptiveResult
from .pipeline.material_ingestion import process_teacher_material
from .pipeline.grading_pipeline import grade_submission
from .pipeline.vector_store import get_chunks_for_material
from .serializers import (
    TeacherMaterialSerializer,
    TeacherMaterialUploadSerializer,
    ExamSerializer,
    SubmitAnswerSerializer,
    SubmissionSerializer,
    DescriptiveResultSerializer,
    SubmissionStudentSerializer,
)
import re
from django.utils import timezone

logger = logging.getLogger(__name__)

class ExamLookupByCodeView(APIView):
    """
    GET /api/student/exams/lookup?code=1234
    Look up an exam by its 4-digit teacher-set access code.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        code = request.query_params.get("code", "").strip()
        if not re.fullmatch(r"\d{4}", code):
            return Response({"detail": "Enter a valid 4-digit exam code."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            exam = Exam.objects.get(access_code=code)
        except Exam.DoesNotExist:
            return Response({"detail": "No exam found with that code."}, status=status.HTTP_404_NOT_FOUND)

        if timezone.now() > exam.valid_until:
            return Response(
                {"detail": f"This exam expired on {exam.valid_until.strftime('%Y-%m-%d %H:%M')} and is no longer accepting submissions."},
                status=status.HTTP_410_GONE,
            )

        return Response(ExamSerializer(exam).data)
class TeacherMaterialUploadView(APIView):
    """
    POST /api/teacher/upload-material

    Accepts a PDF or text file + subject. Saves the file, then
    synchronously runs the ingestion pipeline:
    extract text -> chunk -> embed -> store in ChromaDB -> chunked=True.
    """
    permission_classes = [permissions.IsAuthenticated, IsTeacher]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        serializer = TeacherMaterialUploadSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        material = serializer.save()

        try:
            summary = process_teacher_material(material)
        except Exception as exc:
            logger.exception("Material ingestion failed for material_id=%s", material.id)
            return Response(
                {
                    "material": TeacherMaterialSerializer(material).data,
                    "error": f"Upload saved, but chunking/embedding failed: {exc}",
                },
                status=status.HTTP_207_MULTI_STATUS,
            )

        return Response(
            {
                "material": TeacherMaterialSerializer(material).data,
                "ingestion": summary,
            },
            status=status.HTTP_201_CREATED,
        )


class TeacherMaterialListView(generics.ListAPIView):
    """GET /api/teacher/materials -> materials uploaded by the current teacher"""
    permission_classes = [permissions.IsAuthenticated, IsTeacher]
    serializer_class = TeacherMaterialSerializer

    def get_queryset(self):
        return TeacherMaterial.objects.filter(teacher=self.request.user).order_by("-uploaded_at")


class ExamCreateView(generics.CreateAPIView):
    """POST /api/teacher/create-exam -> create exam with nested questions/rubrics"""
    permission_classes = [permissions.IsAuthenticated, IsTeacher]
    serializer_class = ExamSerializer


class ExamListView(generics.ListAPIView):
    """GET /api/teacher/exams -> exams created by the current teacher"""
    permission_classes = [permissions.IsAuthenticated, IsTeacher]
    serializer_class = ExamSerializer

    def get_queryset(self):
        return Exam.objects.filter(teacher=self.request.user).order_by("-created_at")


class StudentSubmitAnswerView(APIView):
    """
    POST /api/student/submit-answer
    Body (multipart/form-data): exam_id, question_id, image_file

    Creates (or reuses) the student's Submission for this exam, then
    runs the full grading pipeline synchronously for the uploaded image:
    preprocess -> OCR -> RAG -> LLM grading -> save DescriptiveResult.
    """
    permission_classes = [permissions.IsAuthenticated, IsStudent]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        serializer = SubmitAnswerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        exam = serializer.validated_data["exam"]
        question = serializer.validated_data["question"]
        image_file = serializer.validated_data["image_file"]

        submission, _ = Submission.objects.get_or_create(
            student=request.user,
            exam=exam,
            defaults={"status": "pending"},
        )

        # Save the uploaded image to media/ so the pipeline (and any
        # later manual review) can reference it by path.
        import os
        from django.core.files.storage import default_storage

        save_path = f"answer_sheets/sub{submission.id}_q{question.id}_{image_file.name}"
        saved_name = default_storage.save(save_path, image_file)
        full_path = default_storage.path(saved_name)

        try:
            result = grade_submission(submission, question, full_path)
        except Exception as exc:
            logger.exception("Grading pipeline crashed for submission=%s question=%s",
                              submission.id, question.id)
            return Response(
                {"error": f"Grading pipeline failed: {exc}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            {
                "submission": SubmissionSerializer(submission).data,
                "result": DescriptiveResultSerializer(result).data,
            },
            status=status.HTTP_201_CREATED,
        )


class StudentResultsView(generics.RetrieveAPIView):
    """GET /api/student/results/{exam_id} -> student's own results for that exam"""
    permission_classes = [permissions.IsAuthenticated, IsStudent]
    serializer_class = SubmissionSerializer
    lookup_url_kwarg = "exam_id"

    def get_object(self):
        exam_id = self.kwargs["exam_id"]
        submission = Submission.objects.filter(
            student=self.request.user, exam_id=exam_id
        ).first()
        if submission is None:
            from rest_framework.exceptions import NotFound
            raise NotFound("No submission found for this exam.")
        return submission


class TeacherExamResultsView(generics.ListAPIView):
    """GET /api/teacher/results/{exam_id} -> all student results for an exam"""
    permission_classes = [permissions.IsAuthenticated, IsTeacher]
    serializer_class = DescriptiveResultSerializer

    def get_queryset(self):
        exam_id = self.kwargs["exam_id"]
        return DescriptiveResult.objects.filter(
            question__exam_id=exam_id,
            question__exam__teacher=self.request.user,
        ).select_related("submission", "question")


class TeacherExamSubmissionsView(generics.ListAPIView):
    """GET /api/teacher/submissions/{exam_id} -> per-student submissions with results"""
    permission_classes = [permissions.IsAuthenticated, IsTeacher]
    serializer_class = SubmissionStudentSerializer

    def get_queryset(self):
        exam_id = self.kwargs["exam_id"]
        return Submission.objects.filter(
            exam_id=exam_id,
            exam__teacher=self.request.user,
        ).select_related("student").prefetch_related("results__question")

class ExamQuestionsView(generics.RetrieveAPIView):
    """
    GET /api/student/exams/{exam_id}
    Returns the exam plus its full question list (id, text, marks,
    rubric) so a student can see what to answer, and which
    question_id to use when submitting.
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ExamSerializer
    queryset = Exam.objects.all()
    lookup_url_kwarg = "exam_id"
    lookup_field = "id"



class MaterialChunksView(APIView):
    """
    GET /api/teacher/materials/{material_id}/chunks
    Returns the extracted+chunked text stored in ChromaDB for one
    teacher material, so a teacher can verify what the grader will
    actually check student answers against.
    """
    permission_classes = [permissions.IsAuthenticated, IsTeacher]

    def get(self, request, material_id):
        try:
            material = TeacherMaterial.objects.get(id=material_id, teacher=request.user)
        except TeacherMaterial.DoesNotExist:
            return Response({"detail": "Material not found."}, status=status.HTTP_404_NOT_FOUND)

        chunks = get_chunks_for_material(material.id)
        return Response({
            "material_id": material.id,
            "filename": material.filename,
            "chunked": material.chunked,
            "num_chunks": len(chunks),
            "chunks": chunks,
        })