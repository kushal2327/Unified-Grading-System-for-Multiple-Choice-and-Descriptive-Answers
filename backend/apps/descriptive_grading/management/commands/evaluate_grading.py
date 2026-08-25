"""
python manage.py evaluate_grading

Computes the metrics defined in EVALUATION_REPORT_TEMPLATE.md from the
data already sitting in the database — no external tooling required.

Ground truth for accuracy metrics (MAE/RMSE/correlation/etc.) comes from
two sources, in this priority order per result:
  1. DescriptiveResult.ground_truth_marks   — independently graded sample
  2. ManualReviewQueue.override_marks       — reviewer corrections on
                                               flagged/disputed results

Usage:
    python manage.py evaluate_grading
    python manage.py evaluate_grading --exam-id 4
    python manage.py evaluate_grading --subject Physics
    python manage.py evaluate_grading --csv out.csv
    python manage.py evaluate_grading --json out.json
"""
import csv
import json
import statistics
from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db.models import Q

from apps.descriptive_grading.models import DescriptiveResult
from apps.manual_review.models import ManualReviewQueue


def pearson(xs, ys):
    n = len(xs)
    if n < 2:
        return None
    mx, my = statistics.mean(xs), statistics.mean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = sum((x - mx) ** 2 for x in xs) ** 0.5
    dy = sum((y - my) ** 2 for y in ys) ** 0.5
    if dx == 0 or dy == 0:
        return None
    return num / (dx * dy)


def pct(part, whole):
    return round(100 * part / whole, 1) if whole else None


class Command(BaseCommand):
    help = "Compute evaluation metrics for the descriptive grading pipeline."

    def add_arguments(self, parser):
        parser.add_argument("--exam-id", type=int, default=None)
        parser.add_argument("--subject", type=str, default=None)
        parser.add_argument("--csv", type=str, default=None,
                             help="Path to write per-result raw data as CSV.")
        parser.add_argument("--json", type=str, default=None,
                             help="Path to write the summary metrics as JSON.")

    def handle(self, *args, **opts):
        qs = DescriptiveResult.objects.select_related(
            "question", "question__exam", "submission"
        )
        if opts["exam_id"]:
            qs = qs.filter(question__exam_id=opts["exam_id"])
        if opts["subject"]:
            qs = qs.filter(question__exam__subject__iexact=opts["subject"])

        results = list(qs)
        if not results:
            self.stdout.write(self.style.WARNING("No DescriptiveResult rows match the given filters."))
            return

        override_by_result = dict(
            ManualReviewQueue.objects.filter(
                result_id__in=[r.id for r in results], override_marks__isnull=False
            ).values_list("result_id", "override_marks")
        )

        n_total = len(results)
        graded = [r for r in results if r.marks_awarded is not None]
        flagged = [r for r in results if r.flagged]

        # ---- 3.1 OCR quality ----
        ocr_conf = [r.ocr_confidence for r in results if r.ocr_confidence is not None]
        low_ocr_flagged = [r for r in flagged if r.flag_reason == "low_ocr_confidence"]

        # ---- 3.2 Retrieval & relevance ----
        sims = [r.similarity_score for r in results if r.similarity_score is not None]
        low_sim_flagged = [r for r in flagged if r.flag_reason == "low_similarity"]

        # ---- 3.3 LLM grading validity ----
        invalid_range = [r for r in graded if not (0 <= r.marks_awarded <= r.total_marks)]
        llm_invalid_flagged = [r for r in flagged if r.flag_reason == "llm_invalid"]

        # ---- 3.4 End-to-end accuracy vs ground truth ----
        pairs = []  # (system_marks, ground_truth_marks, total_marks)
        for r in results:
            gt = r.ground_truth_marks
            if gt is None:
                gt = override_by_result.get(r.id)
            if gt is not None and r.marks_awarded is not None:
                pairs.append((r.marks_awarded, gt, r.total_marks))

        acc_metrics = {}
        if pairs:
            sys_m = [p[0] for p in pairs]
            gt_m = [p[1] for p in pairs]
            diffs = [abs(s - g) for s, g in zip(sys_m, gt_m)]
            sq_diffs = [(s - g) ** 2 for s, g in zip(sys_m, gt_m)]
            acc_metrics = {
                "n": len(pairs),
                "mae": round(statistics.mean(diffs), 3),
                "rmse": round(statistics.mean(sq_diffs) ** 0.5, 3),
                "pearson_r": round(pearson(sys_m, gt_m), 3) if pearson(sys_m, gt_m) is not None else None,
                "exact_match_rate": pct(sum(1 for d in diffs if d == 0), len(pairs)),
                "within_1_mark_rate": pct(sum(1 for d in diffs if d <= 1), len(pairs)),
            }

        # ---- 3.6 Flag breakdown ----
        flag_counts = defaultdict(int)
        for r in flagged:
            flag_counts[r.flag_reason or "unspecified"] += 1

        # ---- Print report ----
        w = self.stdout.write
        w(self.style.SUCCESS(f"\n=== Evaluation over {n_total} DescriptiveResult rows ==="))

        w("\n-- 3.1 OCR Quality --")
        if ocr_conf:
            w(f"  mean confidence      : {round(statistics.mean(ocr_conf), 1)}")
            w(f"  min confidence       : {round(min(ocr_conf), 1)}")
            w(f"  low-confidence rate  : {pct(len(low_ocr_flagged), n_total)}%")
        else:
            w("  no ocr_confidence data recorded")

        w("\n-- 3.2 Retrieval & Relevance --")
        if sims:
            w(f"  mean similarity      : {round(statistics.mean(sims), 3)}")
            w(f"  low-similarity rate  : {pct(len(low_sim_flagged), n_total)}%")
        else:
            w("  no similarity_score data recorded")

        w("\n-- 3.3 LLM Grading Validity --")
        w(f"  score validity rate  : {pct(len(graded) - len(invalid_range), len(graded))}%"
          if graded else "  no graded results yet")
        w(f"  llm_invalid flags    : {len(llm_invalid_flagged)}")

        w("\n-- 3.4 End-to-End Accuracy (vs ground truth / review overrides) --")
        if acc_metrics:
            for k, v in acc_metrics.items():
                w(f"  {k:20s}: {v}")
        else:
            w("  No ground truth available yet.")
            w("  -> Set DescriptiveResult.ground_truth_marks on a sample, or")
            w("     grade some flagged items via manual review (override_marks).")

        w("\n-- 3.6 Flagging Breakdown --")
        if flag_counts:
            for reason, count in sorted(flag_counts.items()):
                w(f"  {reason:20s}: {count}  ({pct(count, n_total)}%)")
            w(f"  {'TOTAL':20s}: {len(flagged)}  ({pct(len(flagged), n_total)}%)")
        else:
            w("  none flagged")

        # ---- Optional exports ----
        if opts["csv"]:
            with open(opts["csv"], "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "result_id", "exam", "question_id", "ocr_confidence",
                    "similarity_score", "marks_awarded", "total_marks",
                    "ground_truth_marks", "flagged", "flag_reason",
                ])
                for r in results:
                    gt = r.ground_truth_marks or override_by_result.get(r.id)
                    writer.writerow([
                        r.id, r.question.exam.title, r.question_id, r.ocr_confidence,
                        r.similarity_score, r.marks_awarded, r.total_marks,
                        gt, r.flagged, r.flag_reason,
                    ])
            w(self.style.SUCCESS(f"\nRaw per-result data written to {opts['csv']}"))

        if opts["json"]:
            summary = {
                "n_total": n_total,
                "ocr": {
                    "mean_confidence": round(statistics.mean(ocr_conf), 1) if ocr_conf else None,
                    "min_confidence": round(min(ocr_conf), 1) if ocr_conf else None,
                    "low_confidence_rate_pct": pct(len(low_ocr_flagged), n_total),
                },
                "retrieval": {
                    "mean_similarity": round(statistics.mean(sims), 3) if sims else None,
                    "low_similarity_rate_pct": pct(len(low_sim_flagged), n_total),
                },
                "grading_validity": {
                    "score_validity_rate_pct": pct(len(graded) - len(invalid_range), len(graded)) if graded else None,
                    "llm_invalid_flags": len(llm_invalid_flagged),
                },
                "accuracy_vs_ground_truth": acc_metrics or None,
                "flag_breakdown": dict(flag_counts),
            }
            with open(opts["json"], "w") as f:
                json.dump(summary, f, indent=2)
            w(self.style.SUCCESS(f"Summary metrics written to {opts['json']}"))
