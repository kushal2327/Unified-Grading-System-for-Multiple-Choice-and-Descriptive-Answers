# Unified Grading System - Evaluation Report Template

**Project**: Unified Grading System for Multiple-Choice and Descriptive Answers
**Date**: 2026-08-24
**Version**: 1.0

---

## 1. Executive Summary

Brief overview of the system, evaluation objectives, and key findings.

| Item | Details |
|------|---------|
| System Name | Unified Grading System |
| Evaluation Period | [Start Date] – [End Date] |
| Evaluator(s) | [Names] |
| Dataset Size | [N] descriptive answers across [M] questions |
| Questions Covered | [List question IDs/topics] |

---

## 2. System Architecture Overview

### 2.1 Grading Pipeline Flow
```
Answer Sheet Image
        │
        ▼
┌───────────────────┐
│  Vision OCR       │  (Qwen2.5-VL via Ollama)
│  - Transcription  │
│  - Confidence     │
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│  RAG Retrieval    │  (ChromaDB + sentence-transformers)
│  - Similarity     │
│  - Relevance      │
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│  LLM Grading      │  (Ollama llama3 / OpenAI GPT-3.5)
│  - Marks          │
│  - Justification  │
│  - Feedback       │
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│  Validation &     │
│  Flagging         │
└───────────────────┘
```

### 2.2 Key Components
| Component | Technology | Configuration |
|-----------|------------|---------------|
| OCR | Qwen2.5-VL (Ollama) | Vision prompt + JSON output |
| Embeddings | sentence-transformers | Default model (all-MiniLM-L6-v2) |
| Vector Store | ChromaDB | Persistent, subject-partitioned |
| LLM (Primary) | Ollama llama3 | Local inference |
| LLM (Fallback) | OpenAI GPT-3.5 | Cloud API |
| Framework | Django + DRF | PostgreSQL backend |

---

## 3. Evaluation Metrics

### 3.1 OCR Quality Metrics

| Metric | Definition | Target | Actual | Status |
|--------|------------|--------|--------|--------|
| OCR Confidence (mean) | Avg. VLM self-reported confidence | ≥ 70 | [ ] | [ ] |
| OCR Confidence (min) | Minimum confidence across samples | ≥ 50 | [ ] | [ ] |
| Low Confidence Rate | % samples below threshold (60) | < 10% | [ ] | [ ] |
| Transcription Accuracy* | Char/word-level vs. ground truth | ≥ 90% | [ ] | [ ] |

*Requires manually transcribed ground truth

### 3.2 Retrieval & Relevance Metrics

| Metric | Definition | Threshold | Actual | Status |
|--------|------------|-----------|--------|--------|
| Similarity Score (mean) | Best cosine sim. to teacher material | ≥ 0.45 | [ ] | [ ] |
| Context Availability Rate | % answers with relevant context | > 80% | [ ] | [ ] |
| Answer Relevance (mean) | Question-answer cosine similarity | ≥ 0.40 | [ ] | [ ] |
| Off-Topic Detection Rate | % correctly flagged off-topic | 100% | [ ] | [ ] |
| False Positive Rate | On-topic answers flagged as off-topic | < 5% | [ ] | [ ] |

### 3.3 LLM Grading Metrics

| Metric | Definition | Target | Actual | Status |
|--------|------------|--------|--------|--------|
| Score Validity Rate | % LLM scores within [0, total_marks] | 100% | [ ] | [ ] |
| Clamp Rate | % scores requiring clamping | 0% | [ ] | [ ] |
| JSON Parse Success Rate | % valid JSON on first attempt | > 95% | [ ] | [ ] |
| Retry Rate | % requiring re-prompt | < 5% | [ ] | [ ] |
| Marking Consistency* | Std. dev. across repeated grading | Low | [ ] | [ ] |

*Run same answer 3-5 times

### 3.4 End-to-End Accuracy Metrics (Requires Ground Truth)

| Metric | Definition | Target | Actual |
|--------|------------|--------|--------|
| MAE (Mean Absolute Error) | Avg. \|LLM_marks - Teacher_marks\| | < 1.0 | [ ] |
| RMSE | Root mean squared error | < 1.5 | [ ] |
| Correlation (Pearson) | LLM vs. teacher marks | > 0.85 | [ ] |
| Exact Match Rate | % exactly matching teacher marks | > 60% | [ ] |
| Within-1-Mark Rate | % within ±1 mark of teacher | > 85% | [ ] |
| Weighted Kappa | Agreement accounting for chance | > 0.80 | [ ] |

### 3.5 System Performance Metrics

| Metric | Definition | Target | Actual |
|--------|------------|--------|--------|
| Avg. Processing Time | End-to-end latency per answer | < 30s | [ ] |
| OCR Time | Vision model inference | < 15s | [ ] |
| RAG Time | Embedding + ChromaDB query | < 3s | [ ] |
| LLM Time | Grading inference | < 10s | [ ] |
| Throughput | Answers/hour | > 100 | [ ] |
| Memory Usage | Peak RAM during grading | < 4GB | [ ] |

### 3.6 Flagging & Manual Review Metrics

| Flag Reason | Count | Rate | Resolution Time |
|-------------|-------|------|-----------------|
| low_ocr_confidence | [ ] | [ ] | [ ] |
| low_similarity | [ ] | [ ] | [ ] |
| off_topic | [ ] | [ ] | [ ] |
| llm_invalid | [ ] | [ ] | [ ] |
| invalid_score_range | [ ] | [ ] | [ ] |
| **Total** | [ ] | [ ] | [ ] |

---

## 4. Experimental Setup

### 4.1 Dataset Description
| Attribute | Details |
|-----------|---------|
| Total Submissions | [N] |
| Unique Students | [N] |
| Unique Exams | [N] |
| Questions per Exam | [Range] |
| Marks per Question | [Range] |
| Subjects | [List] |
| Handwriting Styles | [Print/Cursive/Mixed] |
| Image Quality | [Good/Fair/Poor distribution] |

### 4.2 Ground Truth Collection
- **Method**: [Double-blind teacher grading / Expert panel / Consensus]
- **Graders**: [N] teachers, [credentials]
- **Inter-rater Reliability**: [Cohen's Kappa / ICC = X.XX]
- **Disagreement Resolution**: [Third grader / Discussion / Average]

### 4.3 Hardware & Software Environment
| Component | Specification |
|-----------|---------------|
| CPU | [e.g., AMD Ryzen 7 5800X] |
| GPU | [e.g., NVIDIA RTX 3080 10GB] |
| RAM | [e.g., 32GB DDR4] |
| OS | [Ubuntu 22.04 / Windows 11] |
| Ollama Version | [e.g., 0.1.47] |
| Models | llama3:8b, qwen2.5vl:3b |

---

## 5. Results

### 5.1 Overall Performance Summary
| Metric Category | Score | Grade |
|-----------------|-------|-------|
| OCR Quality | [X/100] | [A-F] |
| Retrieval Relevance | [X/100] | [A-F] |
| Grading Accuracy | [X/100] | [A-F] |
| System Reliability | [X/100] | [A-F] |
| **Overall** | [X/100] | [A-F] |

### 5.2 Per-Question Analysis
| Question ID | Topic | Total Marks | N Samples | MAE | RMSE | Correlation | Flag Rate |
|-------------|-------|-------------|-----------|-----|------|-------------|-----------|
| Q1 | [Topic] | [M] | [N] | [ ] | [ ] | [ ] | [ ] |
| Q2 | [Topic] | [M] | [N] | [ ] | [ ] | [ ] | [ ] |
| ... | ... | ... | ... | ... | ... | ... | ... |

### 5.3 Per-Subject Analysis
| Subject | N Samples | MAE | Avg. Similarity | Flag Rate |
|---------|-----------|-----|-----------------|-----------|
| [Subject 1] | [ ] | [ ] | [ ] | [ ] |
| [Subject 2] | [ ] | [ ] | [ ] | [ ] |

### 5.4 Error Analysis

#### 5.4.1 Major Error Categories
| Category | Frequency | Example | Root Cause |
|----------|-----------|---------|------------|
| [e.g., Missed key concept] | [N] | [Quote] | [RAG retrieval / LLM reasoning / Rubric ambiguity] |
| [e.g., Over-grading partial] | [N] | [Quote] | [Rubric interpretation / LLM leniency] |
| [e.g., Off-topic false positive] | [N] | [Quote] | [Embedding similarity / Threshold] |

#### 5.4.2 Confusion Matrix (if categorical grades)
| | Teacher: Fail | Teacher: Pass | Teacher: Distinction |
|---|---------------|---------------|---------------------|
| **LLM: Fail** | [ ] | [ ] | [ ] |
| **LLM: Pass** | [ ] | [ ] | [ ] |
| **LLM: Distinction** | [ ] | [ ] | [ ] |

---

## 6. Ablation Studies (Optional)

### 6.1 Component Contribution
| Configuration | MAE | RMSE | Correlation | Notes |
|---------------|-----|------|-------------|-------|
| Full Pipeline | [ ] | [ ] | [ ] | Baseline |
| No RAG (LLM only) | [ ] | [ ] | [ ] | |
| No OCR Confidence Gate | [ ] | [ ] | [ ] | |
| Different Similarity Threshold | [ ] | [ ] | [ ] | e.g., 0.35, 0.55 |
| Different Relevance Threshold | [ ] | [ ] | [ ] | e.g., 0.30, 0.50 |

### 6.2 LLM Provider Comparison
| Provider | Model | MAE | Latency | Cost/Answer | JSON Reliability |
|----------|-------|-----|---------|-------------|------------------|
| Ollama | llama3:8b | [ ] | [ ] | $0 | [ ] |
| OpenAI | gpt-3.5-turbo | [ ] | [ ] | [$] | [ ] |
| OpenAI | gpt-4o-mini | [ ] | [ ] | [$] | [ ] |

---

## 7. Discussion

### 7.1 Strengths
- [e.g., Strong off-topic detection prevents hallucinated grading]
- [e.g., RAG grounding reduces factual errors]
- [e.g., Vision OCR handles cursive handwriting well]

### 7.2 Limitations
- [e.g., Struggles with diagram-heavy answers]
- [e.g., Rubric interpretation varies with phrasing]
- [e.g., Low similarity threshold admits noisy context]

### 7.3 Failure Case Examples
| Case | Input | Expected | Actual | Analysis |
|------|-------|----------|--------|----------|
| 1 | [Description] | [Marks] | [Marks] | [Why] |
| 2 | [Description] | [Marks] | [Marks] | [Why] |

### 7.4 Threshold Sensitivity
- **Similarity Threshold**: Impact on context availability vs. noise
- **Relevance Threshold**: Trade-off between off-topic catch rate and false positives
- **OCR Confidence**: Impact on flag rate vs. auto-grade rate

---

## 8. Recommendations

### 8.1 Immediate Improvements
- [ ] [e.g., Fine-tune similarity threshold per subject]
- [ ] [e.g., Add few-shot examples to grading prompt]
- [ ] [e.g., Implement ensemble grading (multiple LLM calls)]

### 8.2 Medium-Term Enhancements
- [ ] [e.g., Train domain-specific embedding model]
- [ ] [e.g., Add diagram/figure understanding via VLM]
- [ ] [e.g., Implement active learning for threshold optimization]

### 8.3 Long-Term Research
- [ ] [e.g., Multi-modal grading (text + diagrams)]
- [ ] [e.g., Student-specific calibration]
- [ ] [e.g., Explainable grading with citation tracking]

---

## 9. Appendices

### Appendix A: Configuration Parameters
```python
# From backend/config/settings.py
SIMILARITY_THRESHOLD = 0.45
ANSWER_RELEVANCE_THRESHOLD = 0.40
TOP_K_CHUNKS = 3
OCR_CONFIDENCE_THRESHOLD = 60
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
LLM_PROVIDER = "ollama"
OLLAMA_MODEL = "llama3"
OLLAMA_VISION_MODEL = "qwen2.5vl:3b"
```

### Appendix B: Prompt Templates
**Vision OCR Prompt**: (see `vision_ocr.py:21-25`)
**Grading Prompt**: (see `llm_grader.py:39-66`)

### Appendix C: Statistical Test Results
| Test | Statistic | p-value | Significant (α=0.05) |
|------|-----------|---------|---------------------|
| Shapiro-Wilk (normality) | [ ] | [ ] | [ ] |
| Wilcoxon Signed-Rank | [ ] | [ ] | [ ] |
| Kruskal-Wallis (across questions) | [ ] | [ ] | [ ] |

### Appendix D: Sample Outputs
**Sample 1 - Good Grading**
- Question: [Text]
- Student Answer: [OCR text]
- Teacher Marks: [X/Y]
- LLM Marks: [X/Y]
- Justification: [JSON]

**Sample 2 - Flagged Case**
- Flag Reason: [Reason]
- Details: [Explanation]

---

## 10. References
1. [Paper/Project references]
2. [Dataset citations]
3. [Tool/library citations]

---

*Report generated using automated template. Fill in [bracketed] sections with actual data.*