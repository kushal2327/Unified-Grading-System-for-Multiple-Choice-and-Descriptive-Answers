from rest_framework import serializers

from .models import TeacherMaterial, Exam, Question, Submission, DescriptiveResult


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
        read_only_fields = ["id"]
        extra_kwargs = {"exam": {"required": False}}


class ExamSerializer(serializers.ModelSerializer):
    questions = QuestionSerializer(many=True, required=False)

    class Meta:
        model = Exam
        fields = ["id", "title", "subject", "teacher", "created_at", "questions"]
        read_only_fields = ["id", "teacher", "created_at"]

    def create(self, validated_data):
        questions_data = validated_data.pop("questions", [])
        exam = Exam.objects.create(
            title=validated_data["title"],
            subject=validated_data["subject"],
            teacher=self.context["request"].user,
        )
        for q in questions_data:
            Question.objects.create(exam=exam, **q)
        return exam


class DescriptiveResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = DescriptiveResult
        fields = [
            "id", "submission", "question",
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

        try:
            question = Question.objects.get(id=attrs["question_id"], exam=exam)
        except Question.DoesNotExist:
            raise serializers.ValidationError({"question_id": "Question not found for this exam."})

        attrs["exam"] = exam
        attrs["question"] = question
        return attrs


class SubmissionSerializer(serializers.ModelSerializer):
    results = DescriptiveResultSerializer(many=True, read_only=True)

    class Meta:
        model = Submission
        fields = ["id", "student", "exam", "submitted_at", "status", "results"]
        read_only_fields = ["id", "student", "submitted_at", "status"]
