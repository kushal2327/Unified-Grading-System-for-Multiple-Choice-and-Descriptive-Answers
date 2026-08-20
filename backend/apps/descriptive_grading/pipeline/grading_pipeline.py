"""
apps/descriptive_grading/pipeline/grading_pipeline.py

Orchestrates the full Phase 2 pipeline for a single student answer
image: preprocessing -> OCR -> RAG retrieval -> LLM grading ->
score validation -> saving results + flagging.
"""
import logging

from django.conf import settings

from ..models import DescriptiveResult
from apps.manual_review.models import ManualReviewQueue
from .rag import retrieve_context, compute_answer_relevance
from .llm_grader import build_prompt, grade_with_llm, validate_score, LLMGradingError
from .vision_ocr import extract_and_clean

logger = logging.getLogger(__name__)


def _flag(result, reason, message):
    result.flagged = True
    result.flag_reason = reason
    result.save(update_fields=["flagged", "flag_reason"])
    ManualReviewQueue.objects.create(result=result, reason=reason)
    logger.info("Flagged descriptive_result %s: %s (%s)", result.id, reason, message)


def _teacher_material_exists(subject):
    from ..models import TeacherMaterial
    return TeacherMaterial.objects.filter(subject=subject, chunked=True).exists()


def grade_submission(submission, question, image_path):
    """
    Run the full grading pipeline for one (submission, question, image)
    and return the created DescriptiveResult.
    """
    result = DescriptiveResult.objects.create(
        submission=submission,
        question=question,
        total_marks=question.total_marks,
    )

    ocr_result = extract_and_clean(image_path)

    result.ocr_raw_text = ocr_result["raw_text"]
    result.ocr_cleaned_text = ocr_result["cleaned_text"]
    result.ocr_confidence = ocr_result["confidence"]
    result.save(update_fields=["ocr_raw_text", "ocr_cleaned_text", "ocr_confidence"])

    if ocr_result["below_threshold"]:
        _flag(result, "low_ocr_confidence",
              f"OCR confidence {ocr_result['confidence']:.1f} < {settings.OCR_CONFIDENCE_THRESHOLD}")
        submission.status = "flagged"
        submission.save(update_fields=["status"])
        return result

    subject = question.exam.subject
    rag_result = retrieve_context(question.question_text, subject)

    result.similarity_score = rag_result["similarity_score"]
    result.retrieved_chunks = rag_result["retrieved_chunks"]
    result.save(update_fields=["similarity_score", "retrieved_chunks"])

    material_exists_for_subject = _teacher_material_exists(subject)
    if not rag_result["context_available"] and material_exists_for_subject:
        _flag(result, "low_similarity",
              f"similarity {rag_result['similarity_score']:.2f} < {settings.SIMILARITY_THRESHOLD}")

    # Detect off-topic answers BEFORE LLM grading. The retrieval topic is
    # fixed by the question; here we check whether the student actually
    # answered the question. If not, award zero marks.
    answer_relevance = compute_answer_relevance(question.question_text,
                                                ocr_result["cleaned_text"])
    if answer_relevance < settings.ANSWER_RELEVANCE_THRESHOLD:
        result.marks_awarded = 0.0
        result.feedback = (
            "The submitted answer does not address the question. "
            "It appears to be about a different topic, so no marks are awarded."
        )
        result.justification = {
            "relevance": {
                "status": "none",
                "marks": 0,
                "comment": (
                    f"Answer-to-question relevance was {answer_relevance:.2f} "
                    f"(below threshold {settings.ANSWER_RELEVANCE_THRESHOLD}); the "
                    "answer covers a different topic than the question asks about."
                ),
            }
        }
        result.save(update_fields=["marks_awarded", "feedback", "justification"])
        _flag(result, "off_topic",
              f"answer relevance {answer_relevance:.2f} < {settings.ANSWER_RELEVANCE_THRESHOLD}")
        submission.status = "graded"
        submission.save(update_fields=["status"])
        return result

    prompt = build_prompt(
        question_text=question.question_text,
        rubric=question.rubric,
        total_marks=question.total_marks,
        student_answer=ocr_result["cleaned_text"],
        context_available=rag_result["context_available"],
        combined_context=rag_result["combined_context"],
    )

    try:
        llm_response = grade_with_llm(prompt)
    except LLMGradingError as exc:
        _flag(result, "llm_invalid", str(exc))
        submission.status = "flagged"
        submission.save(update_fields=["status"])
        return result

    justification = llm_response.get("justification", {})
    justification_sum = sum(
        pt.get("marks", 0) for pt in justification.values() if isinstance(pt, dict)
    )

    score_check = validate_score(llm_response, question.total_marks)

    if justification and justification_sum > 0:
        result.marks_awarded = min(justification_sum, float(question.total_marks))
    else:
        result.marks_awarded = score_check["marks"]
    result.feedback = llm_response.get("feedback", "")
    result.justification = justification
    result.save(update_fields=["marks_awarded", "feedback", "justification"])

    if score_check["was_clamped"]:
        _flag(result, "invalid_score_range",
              f"LLM returned marks={llm_response.get('marks')} outside [0, {question.total_marks}]")
        submission.status = "flagged"
    else:
        submission.status = "graded"

    submission.save(update_fields=["status"])
    return result
