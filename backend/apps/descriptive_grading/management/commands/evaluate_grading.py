"""
python manage.py evaluate_grading

Computes evaluation metrics for the descriptive grading pipeline directly
from the database — no external tooling or ML libraries required.

Ground truth for accuracy/precision/recall/F1/MAE comes from
DescriptiveResult.ground_truth_marks — marks a teacher assigns to the same
answer independently, entered via the Django admin (or a CSV import you run
separately). Results without ground_truth_marks set are excluded from the
accuracy section only; every other section still uses the full dataset.

Two families of accuracy metric are reported, because "marks" is a
continuous value but accuracy/precision/recall/F1 are classification
metrics:

  - Regression metrics (system marks vs teacher marks directly):
      MAE, RMSE, Pearson r, exact-match rate, within-1-mark rate.

  - Classification metrics (system marks vs teacher marks, binned):
      * Pass/Fail  — binary, threshold = --pass-ratio (default 0.4) of
        total_marks. Reports accuracy, precision, recall, F1, and the
        confusion matrix.
      * Grade band — multiclass (A-F, matching the score bands already
        used on the review dashboard). Reports per-class and macro
        accuracy/precision/recall/F1.

Two additional sections are available without ground truth:

  - Score–Similarity Correlation: Pearson r between normalised score
    ratio and retrieval similarity_score (no teacher marks needed).

  - Self-Consistency: re-grade sampled results N times to measure
    LLM scoring variance. Requires --consistency-runs > 0.

Usage:
    python manage.py evaluate_grading
    python manage.py evaluate_grading --exam-id 4
    python manage.py evaluate_grading --subject Physics
    python manage.py evaluate_grading --pass-ratio 0.5
    python manage.py evaluate_grading --csv out.csv
    python manage.py evaluate_grading --json out.json
    python manage.py evaluate_grading --consistency-runs 5
    python manage.py evaluate_grading --consistency-runs 3 --consistency-sample 10
"""
import csv
import json
import random
import statistics
from collections import defaultdict

from django.core.management.base import BaseCommand

from apps.descriptive_grading.models import DescriptiveResult
from apps.descriptive_grading.pipeline.llm_grader import build_prompt, grade_with_llm, validate_score

GRADE_BANDS = [
    ("A", 0.81, 1.01),   # 81-100%
    ("B", 0.61, 0.81),   # 61-80%
    ("C", 0.41, 0.61),   # 41-60%
    ("D", 0.21, 0.41),   # 21-40%
    ("F", 0.00, 0.21),   # 0-20%
]


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


def grade_band(marks, total, bands):
    if total <= 0:
        return None
    ratio = marks / total
    for label, lo, hi in bands:
        if lo <= ratio < hi:
            return label
    return bands[0][0] if ratio >= bands[0][1] else bands[-1][0]


def binary_metrics(pairs_bool):
    """pairs_bool: list of (predicted_bool, actual_bool). Returns confusion
    matrix + accuracy/precision/recall/F1 for the positive (True) class."""
    tp = sum(1 for p, a in pairs_bool if p and a)
    fp = sum(1 for p, a in pairs_bool if p and not a)
    tn = sum(1 for p, a in pairs_bool if not p and not a)
    fn = sum(1 for p, a in pairs_bool if not p and a)
    n = len(pairs_bool)
    accuracy = pct(tp + tn, n)
    precision = round(tp / (tp + fp), 3) if (tp + fp) else None
    recall = round(tp / (tp + fn), 3) if (tp + fn) else None
    f1 = (round(2 * precision * recall / (precision + recall), 3)
          if precision and recall and (precision + recall) > 0 else None)
    return {
        "n": n, "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        "accuracy_pct": accuracy, "precision": precision,
        "recall": recall, "f1": f1,
    }


def multiclass_metrics(pairs_label, labels):
    """pairs_label: list of (predicted_label, actual_label)."""
    n = len(pairs_label)
    correct = sum(1 for p, a in pairs_label if p == a)
    per_class = {}
    precisions, recalls, f1s = [], [], []
    for lab in labels:
        tp = sum(1 for p, a in pairs_label if p == lab and a == lab)
        fp = sum(1 for p, a in pairs_label if p == lab and a != lab)
        fn = sum(1 for p, a in pairs_label if p != lab and a == lab)
        support = sum(1 for _, a in pairs_label if a == lab)
        precision = round(tp / (tp + fp), 3) if (tp + fp) else None
        recall = round(tp / (tp + fn), 3) if (tp + fn) else None
        f1 = (round(2 * precision * recall / (precision + recall), 3)
              if precision and recall and (precision + recall) > 0 else None)
        per_class[lab] = {"support": support, "precision": precision,
                           "recall": recall, "f1": f1}
        if precision is not None:
            precisions.append(precision)
        if recall is not None:
            recalls.append(recall)
        if f1 is not None:
            f1s.append(f1)
    macro = {
        "accuracy_pct": pct(correct, n),
        "macro_precision": round(statistics.mean(precisions), 3) if precisions else None,
        "macro_recall": round(statistics.mean(recalls), 3) if recalls else None,
        "macro_f1": round(statistics.mean(f1s), 3) if f1s else None,
    }
    return per_class, macro


class Command(BaseCommand):
    help = "Compute evaluation metrics for the descriptive grading pipeline."

    def add_arguments(self, parser):
        parser.add_argument("--exam-id", type=int, default=None)
        parser.add_argument("--subject", type=str, default=None)
        parser.add_argument("--pass-ratio", type=float, default=0.4,
                             help="Fraction of total_marks that counts as a pass (default 0.4).")
        parser.add_argument("--csv", type=str, default=None,
                             help="Path to write per-result raw data as CSV.")
        parser.add_argument("--json", type=str, default=None,
                             help="Path to write the summary metrics as JSON.")
        parser.add_argument("--consistency-runs", type=int, default=0,
                             help="Number of re-grading runs per sampled result for self-consistency test (0 = skip).")
        parser.add_argument("--consistency-sample", type=int, default=15,
                             help="Number of results to sample for the self-consistency test (default 15).")
        parser.add_argument("--temperatures", type=float, nargs="+", default=[0.5],
                             help="Temperature values to test in the consistency test (default 0.5). "
                                  "Example: --temperatures 0.3 0.5 0.7 0.9")
        parser.add_argument("--seed", type=int, default=42,
                             help="Random seed for reproducible consistency sampling (default 42).")

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

        pass_ratio = opts["pass_ratio"]
        n_total = len(results)
        graded = [r for r in results if r.marks_awarded is not None]
        flagged = [r for r in results if r.flagged]

        # ---- OCR quality ----
        ocr_conf = [r.ocr_confidence for r in results if r.ocr_confidence is not None]

        # ---- Retrieval & relevance ----
        sims = [r.similarity_score for r in results if r.similarity_score is not None]

        # ---- LLM grading validity ----
        invalid_range = [r for r in graded if not (0 <= r.marks_awarded <= r.total_marks)]

        # ---- Ground-truth pairs (teacher marks vs system marks) ----
        pairs = [
            (r.marks_awarded, r.ground_truth_marks, r.total_marks)
            for r in results
            if r.ground_truth_marks is not None and r.marks_awarded is not None
        ]

        reg_metrics = {}
        pass_fail_metrics = {}
        grade_per_class, grade_macro = {}, {}

        if pairs:
            sys_m = [p[0] for p in pairs]
            gt_m = [p[1] for p in pairs]
            diffs = [abs(s - g) for s, g in zip(sys_m, gt_m)]
            sq_diffs = [(s - g) ** 2 for s, g in zip(sys_m, gt_m)]
            r_val = pearson(sys_m, gt_m)
            reg_metrics = {
                "n": len(pairs),
                "mae": round(statistics.mean(diffs), 3),
                "rmse": round(statistics.mean(sq_diffs) ** 0.5, 3),
                "pearson_r": round(r_val, 3) if r_val is not None else None,
                "exact_match_rate_pct": pct(sum(1 for d in diffs if d == 0), len(pairs)),
                "within_1_mark_rate_pct": pct(sum(1 for d in diffs if d <= 1), len(pairs)),
            }

            pass_pairs = [
                (s >= pass_ratio * t, g >= pass_ratio * t)
                for s, g, t in pairs
            ]
            pass_fail_metrics = binary_metrics(pass_pairs)

            band_pairs = [
                (grade_band(s, t, GRADE_BANDS), grade_band(g, t, GRADE_BANDS))
                for s, g, t in pairs
            ]
            band_labels = [b[0] for b in GRADE_BANDS]
            grade_per_class, grade_macro = multiclass_metrics(band_pairs, band_labels)

        # ---- Flag breakdown ----
        flag_counts = defaultdict(int)
        for r in flagged:
            flag_counts[r.flag_reason or "unspecified"] += 1

        # ---- Score–Similarity Correlation ----
        score_sim_pairs = [
            (r.marks_awarded / r.total_marks, r.similarity_score)
            for r in results
            if r.marks_awarded is not None and r.total_marks and r.similarity_score is not None
            and not (r.flagged and r.marks_awarded == 0)
        ]
        score_sim_r = None
        score_sim_interp = None
        if score_sim_pairs:
            score_ratios = [p[0] for p in score_sim_pairs]
            sim_scores = [p[1] for p in score_sim_pairs]
            score_sim_r = pearson(score_ratios, sim_scores)
            if score_sim_r is not None:
                if score_sim_r < 0.2:
                    score_sim_interp = "weak/no correlation: grading may not be using retrieved context meaningfully"
                elif score_sim_r < 0.4:
                    score_sim_interp = "moderate correlation: acceptable but worth spot-checking"
                else:
                    score_sim_interp = "healthy correlation: scores track retrieval relevance as expected"

        # ---- Self-Consistency / Test-Retest Reliability ----
        consistency_runs = opts["consistency_runs"]
        consistency_sample_size = opts["consistency_sample"]
        temperatures = opts["temperatures"]
        all_temp_results = {}

        if consistency_runs > 0:
            consistency_candidates = [
                r for r in results
                if r.ocr_cleaned_text and r.question.rubric and r.total_marks
            ]
            random.seed(opts["seed"])
            sampled = random.sample(consistency_candidates,
                                    min(consistency_sample_size, len(consistency_candidates)))
            w = self.stdout.write
            w(f"\nRunning self-consistency test: {consistency_runs} runs x {len(sampled)} items"
              f" x {len(temperatures)} temperatures ...")

            for temp in temperatures:
                consistency_items = []
                for r in sampled:
                    prompt = build_prompt(
                        question_text=r.question.question_text,
                        rubric=r.question.rubric,
                        total_marks=r.total_marks,
                        student_answer=r.ocr_cleaned_text,
                        context_available=bool(r.retrieved_chunks),
                        combined_context="\n".join(r.retrieved_chunks) if r.retrieved_chunks else "",
                    )
                    marks_list = []
                    for _ in range(consistency_runs):
                        try:
                            resp = grade_with_llm(prompt, temperature=temp)
                            validated = validate_score(resp, r.total_marks)
                            marks_list.append(validated["marks"])
                        except Exception:
                            marks_list.append(None)

                    valid_marks = [m for m in marks_list if m is not None]
                    if len(valid_marks) >= 2:
                        mean_m = statistics.mean(valid_marks)
                        std_m = statistics.pstdev(valid_marks)
                        spread = max(valid_marks) - min(valid_marks)
                        spread_pct = pct(spread, r.total_marks)
                    else:
                        mean_m = valid_marks[0] if valid_marks else None
                        std_m = 0.0
                        spread = 0.0
                        spread_pct = 0.0

                    item_data = {
                        "result_id": r.id,
                        "question_id": r.question_id,
                        "total_marks": r.total_marks,
                        "original_marks": r.marks_awarded,
                        "mean_marks": round(mean_m, 3) if mean_m is not None else None,
                        "std_dev": round(std_m, 3),
                        "spread": round(spread, 3),
                        "spread_pct": spread_pct,
                        "n_successful": len(valid_marks),
                    }
                    consistency_items.append(item_data)

                successful_items = [i for i in consistency_items if i["n_successful"] >= 2]
                failed_items = [i for i in consistency_items if i["n_successful"] == 0]

                if successful_items:
                    mean_std = statistics.mean([i["std_dev"] for i in successful_items])
                    mean_spread_pct = statistics.mean([i["spread_pct"] for i in successful_items])
                    if mean_spread_pct > 15:
                        stability = "high instability"
                    elif mean_spread_pct >= 5:
                        stability = "moderate variance, consider lowering temperature"
                    else:
                        stability = "stable: grading is reproducible"
                else:
                    mean_std = 0.0
                    mean_spread_pct = 0.0
                    stability = "no successful LLM calls — check Ollama connection"

                consistency_summary = {
                    "n_items": len(consistency_items),
                    "n_successful_items": len(successful_items),
                    "n_failed_items": len(failed_items),
                    "n_runs": consistency_runs,
                    "mean_std": round(mean_std, 3),
                    "mean_spread_pct": round(mean_spread_pct, 1),
                    "stability": stability,
                }

                all_temp_results[temp] = {
                    "summary": consistency_summary,
                    "items": consistency_items,
                }

        consistency_summary = None

        # ---- Print report ----
        w = self.stdout.write
        w(self.style.SUCCESS(f"\n=== Evaluation over {n_total} DescriptiveResult rows ==="))

        w("\n-- OCR Quality --")
        if ocr_conf:
            w(f"  mean confidence      : {round(statistics.mean(ocr_conf), 1)}")
            w(f"  min confidence       : {round(min(ocr_conf), 1)}")
        else:
            w("  no ocr_confidence data recorded")

        w("\n-- Retrieval & Relevance --")
        if sims:
            w(f"  mean similarity      : {round(statistics.mean(sims), 3)}")
        else:
            w("  no similarity_score data recorded")

        w("\n-- LLM Grading Validity --")
        w(f"  score validity rate  : {pct(len(graded) - len(invalid_range), len(graded))}%"
          if graded else "  no graded results yet")

        w("\n-- Accuracy vs Teacher Ground Truth (regression) --")
        if reg_metrics:
            for k, v in reg_metrics.items():
                w(f"  {k:24s}: {v}")
        else:
            w("  No ground_truth_marks set yet.")
            w("  -> Grade a sample of answers as a teacher and set")
            w("     DescriptiveResult.ground_truth_marks via the admin,")
            w("     then re-run this command.")

        w(f"\n-- Pass/Fail Classification (threshold = {int(pass_ratio*100)}% of total marks) --")
        if pass_fail_metrics:
            m = pass_fail_metrics
            w(f"  n                    : {m['n']}")
            w(f"  confusion matrix     : TP={m['tp']} FP={m['fp']} TN={m['tn']} FN={m['fn']}")
            w(f"  accuracy             : {m['accuracy_pct']}%")
            w(f"  precision            : {m['precision']}")
            w(f"  recall               : {m['recall']}")
            w(f"  f1                   : {m['f1']}")
        else:
            w("  No ground truth available yet.")

        w("\n-- Grade-Band Classification (A-F, macro-averaged) --")
        if grade_macro:
            for label in [b[0] for b in GRADE_BANDS]:
                c = grade_per_class[label]
                w(f"  {label}  support={c['support']:<3} precision={c['precision']}"
                  f"  recall={c['recall']}  f1={c['f1']}")
            w(f"  overall accuracy     : {grade_macro['accuracy_pct']}%")
            w(f"  macro precision      : {grade_macro['macro_precision']}")
            w(f"  macro recall         : {grade_macro['macro_recall']}")
            w(f"  macro f1             : {grade_macro['macro_f1']}")
        else:
            w("  No ground truth available yet.")

        w("\n-- Flagging Breakdown --")
        if flag_counts:
            for reason, count in sorted(flag_counts.items()):
                w(f"  {reason:20s}: {count}  ({pct(count, n_total)}%)")
            w(f"  {'TOTAL':20s}: {len(flagged)}  ({pct(len(flagged), n_total)}%)")
        else:
            w("  none flagged")

        w("\n-- Score vs Retrieval-Similarity Correlation --")
        if score_sim_pairs:
            w(f"  n                    : {len(score_sim_pairs)}")
            w(f"  pearson r            : {round(score_sim_r, 3) if score_sim_r is not None else 'N/A'}")
            w(f"  interpretation       : {score_sim_interp}")
        else:
            w("  not enough data (need results with both marks_awarded and similarity_score)")

        if all_temp_results:
            w(f"\n-- Self-Consistency ({consistency_runs} runs x {len(sampled)} items, same sample) --")
            w(f"\n  {'Temperature':>12s}  {'Mean StdDev':>12s}  {'Mean Spread%':>13s}  {'OK/Total':>9s}  {'Stability'}")
            w(f"  {'-'*12}  {'-'*12}  {'-'*13}  {'-'*9}  {'-'*30}")
            for temp in temperatures:
                data = all_temp_results[temp]["summary"]
                w(f"  {temp:>12.1f}  {data['mean_std']:>12.3f}  {data['mean_spread_pct']:>12.1f}%  "
                  f"{data['n_successful_items']:>4d}/{data['n_items']:<4d}  {data['stability']}")
            w("")
            for temp in temperatures:
                data = all_temp_results[temp]
                w(f"\n  --- Temperature {temp} (detailed) ---")
                items = data["items"]
                w(f"  {'result_id':>10s} {'question':>10s} {'orig':>6s} {'mean':>6s} {'std':>6s} {'spread':>8s} {'spread%':>8s} {'ok':>4s}")
                for item in items:
                    orig_str = f"{item['original_marks']:>6}" if item['original_marks'] is not None else "  N/A"
                    mean_str = f"{item['mean_marks']:>6}" if item['mean_marks'] is not None else "  N/A"
                    w(f"  {item['result_id']:>10d} {item['question_id']:>10d} {orig_str} "
                      f"{mean_str} {item['std_dev']:>6} {item['spread']:>8} "
                      f"{item['spread_pct']:>7}% {item['n_successful']:>4d}/{consistency_runs}")
        elif consistency_runs > 0:
            w("\n-- Self-Consistency --")
            w("  no results with ocr_cleaned_text and rubric available for consistency test")

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
                    writer.writerow([
                        r.id, r.question.exam.title, r.question_id, r.ocr_confidence,
                        r.similarity_score, r.marks_awarded, r.total_marks,
                        r.ground_truth_marks, r.flagged, r.flag_reason,
                    ])
            w(self.style.SUCCESS(f"\nRaw per-result data written to {opts['csv']}"))

        if opts["json"]:
            summary = {
                "n_total": n_total,
                "ocr": {
                    "mean_confidence": round(statistics.mean(ocr_conf), 1) if ocr_conf else None,
                },
                "retrieval": {
                    "mean_similarity": round(statistics.mean(sims), 3) if sims else None,
                },
                "grading_validity": {
                    "score_validity_rate_pct": pct(len(graded) - len(invalid_range), len(graded)) if graded else None,
                },
                "accuracy_regression": reg_metrics or None,
                "pass_fail_classification": pass_fail_metrics or None,
                "grade_band_classification": {
                    "per_class": grade_per_class, "macro": grade_macro
                } if grade_macro else None,
                "flag_breakdown": dict(flag_counts),
                "score_similarity_correlation": {
                    "n": len(score_sim_pairs),
                    "pearson_r": round(score_sim_r, 3) if score_sim_r is not None else None,
                    "interpretation": score_sim_interp,
                } if score_sim_pairs else None,
                "self_consistency": {
                    str(temp): data for temp, data in all_temp_results.items()
                } if all_temp_results else None,
            }
            with open(opts["json"], "w") as f:
                json.dump(summary, f, indent=2)
            w(self.style.SUCCESS(f"Summary metrics written to {opts['json']}"))