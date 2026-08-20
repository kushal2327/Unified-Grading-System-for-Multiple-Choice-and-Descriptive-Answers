from rest_framework import serializers

from .models import TeacherMaterial, Exam, Question, Submission, DescriptiveResult
import re
from django.utils import timezone

class TeacherMaterialSerializer(serializers.ModelSerializer):
    class Meta:
        model = TeacherMaterial
        fields = ["id", "subject", "teacher", "filename", "file_path", "uploaded_at", "chunked"]
        read_only_fields = ["id", "teacher", "uploaded_at", "chunked"]


class TeacherMaterialUploadSerializer(serializers.ModelSerializer):
    """Used specifically for the POST /api/teacher/upload-material endpoint."""

    file = serializers.FileField(write_only=True)

    class Meta:
        model = TeacherMaterial
        fields = ["subject", "file"]

    def validate_file(self, value):
        allowed_ext = (".pdf", ".txt", ".md")
        if not value.name.lower().endswith(allowed_ext):
            raise serializers.ValidationError(
                f"Unsupported file type. Allowed: {', '.join(allowed_ext)}"
            )
        return value

    def create(self, validated_data):
        uploaded_file = validated_data.pop("file")
        return TeacherMaterial.objects.create(
            subject=validated_data["subject"],
            teacher=self.context["request"].user,
            filename=uploaded_file.name,
            file_path=uploaded_file,
        )


class QuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = ["id", "exam", "question_text", "total_marks", "rubric"]
        extra_kwargs = {
            "id": {"read_only": False, "required": False},
            "exam": {"required": False},
        }


class ExamSerializer(serializers.ModelSerializer):
    questions = QuestionSerializer(many=True, required=False)

    class Meta:
        model = Exam
        fields = ["id", "title", "subject", "teacher", "access_code", "valid_until", "created_at", "questions"]
        read_only_fields = ["id", "teacher", "created_at"]
        extra_kwargs = {"valid_until": {"required": False}}

    def validate_access_code(self, value):
        if not re.fullmatch(r"\d{4}", value):
            raise serializers.ValidationError("Access code must be exactly 4 digits (e.g. 4821).")
        exists = Exam.objects.filter(access_code=value)
        if self.instance is not None:
            exists = exists.exclude(pk=self.instance.pk)
        if exists.exists():
            raise serializers.ValidationError(
                "This code is already used by another exam. Please choose a different 4-digit code."
            )
        return value

    def create(self, validated_data):
        questions_data = validated_data.pop("questions", [])
        exam_kwargs = {
            "title": validated_data["title"],
            "subject": validated_data["subject"],
            "teacher": self.context["request"].user,
            "access_code": validated_data["access_code"],
        }
        if validated_data.get("valid_until"):
            exam_kwargs["valid_until"] = validated_data["valid_until"]

        exam = Exam.objects.create(**exam_kwargs)
        for q in questions_data:
            Question.objects.create(exam=exam, **q)
        return exam

    def update(self, instance, validated_data):
        questions_data = validated_data.pop("questions", None)

        instance.title = validated_data.get("title", instance.title)
        instance.subject = validated_data.get("subject", instance.subject)
        instance.access_code = validated_data.get("access_code", instance.access_code)
        if validated_data.get("valid_until"):
            instance.valid_until = validated_data["valid_until"]
        instance.save()

        if questions_data is not None:
            for q_data in questions_data:
                q_id = q_data.pop("id", None)
                if q_id is not None:
                    try:
                        question = Question.objects.get(id=q_id, exam=instance)
                    except Question.DoesNotExist:
                        raise serializers.ValidationError({
                            "questions": f"Question {q_id} does not belong to this exam."
                        })
                    for field in ("question_text", "total_marks", "rubric"):
                        if field in q_data:
                            setattr(question, field, q_data[field])
                    question.save()
                else:
                    Question.objects.create(exam=instance, **q_data)

        return instance

class DescriptiveResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = DescriptiveResult
        fields = [
            "id", "submission", "question",
            "answer_sheet",
            "ocr_raw_text", "ocr_cleaned_text", "ocr_confidence",
            "similarity_score", "retrieved_chunks",
            "marks_awarded", "total_marks",
            "feedback", "justification",
            "flagged", "flag_reason", "created_at",
        ]


class SubmitAnswerSerializer(serializers.Serializer):
    """POST /api/student/submit-answer - accepts exam_id, question_id, image_file."""
    exam_id = serializers.IntegerField()
    question_id = serializers.IntegerField()
    image_file = serializers.ImageField()

    def validate(self, attrs):
        try:
            exam = Exam.objects.get(id=attrs["exam_id"])
        except Exam.DoesNotExist:
            raise serializers.ValidationError({"exam_id": "Exam not found."})

        if timezone.now() > exam.valid_until:
            raise serializers.ValidationError({
                "exam_id": f"This exam expired on {exam.valid_until.strftime('%Y-%m-%d %H:%M')} and is no longer accepting submissions."
            })

        try:
            question = Question.objects.get(id=attrs["question_id"], exam=exam)
        except Question.DoesNotExist:
            raise serializers.ValidationError({"question_id": "Question not found for this exam."})

        attrs["exam"] = exam
        attrs["question"] = question
        return attrs


class SubmissionSerializer(serializers.ModelSerializer):
    results = DescriptiveResultSerializer(many=True, read_only=True)
    valid_until = serializers.DateTimeField(source="exam.valid_until", read_only=True)

    class Meta:
        model = Submission
        fields = ["id", "student", "exam", "submitted_at", "status", "valid_until", "results"]
        read_only_fields = ["id", "student", "submitted_at", "status"]


class SubmissionStudentSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.name", read_only=True)
    student_roll = serializers.CharField(source="student.roll_number", read_only=True)
    results = DescriptiveResultSerializer(many=True, read_only=True)

    class Meta:
        model = Submission
        fields = ["id", "student_name", "student_roll", "submitted_at", "status", "results"]
