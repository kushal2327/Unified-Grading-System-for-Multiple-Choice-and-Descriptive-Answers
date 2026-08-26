import { useEffect, useState } from "react";
import { teacherAPI } from "../services/api";
import MaterialsList from "./MaterialsList";
import EditExamCard from "./EditExamCard";

const MEDIA_ORIGIN = new URL(
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000/api"
).origin;

function VisionStatusBadge() {
  const [status, setStatus] = useState(null);
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    teacherAPI.visionStatus()
      .then(({ data }) => setStatus(data))
      .catch(() => setStatus({ error: "Could not check vision model status" }))
      .finally(() => setChecking(false));
  }, []);

  if (checking) return null;

  const ok = status?.ollama_running && status?.vision_model_available;
  return (
    <div className="card" style={{ background: ok ? "#e3ede4" : "#fde8e8", marginBottom: "0.5rem" }}>
      <p style={{ margin: 0, fontSize: "0.85rem" }}>
        <strong>Vision model (handwriting recognition):</strong>{" "}
        {ok ? (
          <span style={{ color: "#2d7a3a" }}>Ready ({status?.vision_model_available ? "qwen2.5vl detected" : "running"})</span>
        ) : (
          <span style={{ color: "#c0392b" }}>
            {status?.error || "Not available — handwritten answers will fail to grade"}
          </span>
        )}
      </p>
      {!ok && (
        <p style={{ margin: "0.4rem 0 0", fontSize: "0.78rem", color: "#888" }}>
          To fix: (1) Start Ollama: <code>ollama serve</code> (2) Pull vision model: <code>ollama pull qwen2.5vl:3b</code>
        </p>
      )}
    </div>
  );
}

function UploadMaterialCard() {
  const [subject, setSubject] = useState("");
  const [file, setFile] = useState(null);
  const [status, setStatus] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file) return;
    setStatus({ type: "loading", message: "Uploading and processing..." });

    const formData = new FormData();
    formData.append("subject", subject);
    formData.append("file", file);

    try {
      const { data } = await teacherAPI.uploadMaterial(formData);
      if (data.error) {
        setStatus({ type: "error", message: data.error });
      } else {
        setStatus({
          type: "success",
          message: `Stored ${data.ingestion?.num_chunks ?? 0} chunks for "${data.material.filename}".`,
        });
        setSubject("");
        setFile(null);
        e.target.reset();
      }
    } catch (err) {
      setStatus({ type: "error", message: err.response?.data?.detail || "Upload failed." });
    }
  };

  return (
    <div className="card">
      <h3>Upload reference material</h3>
      <p className="muted" style={{ marginTop: 0 }}>
        PDF or text notes the grader will check student answers against.
      </p>
      <form onSubmit={handleSubmit}>
        <div className="field">
          <label htmlFor="subject">Subject</label>
          <input id="subject" required value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="e.g. Computer Science" />
        </div>
        <div className="field">
          <label htmlFor="file">File (.pdf or .txt)</label>
          <input id="file" type="file" accept=".pdf,.txt,.md" required
            onChange={(e) => setFile(e.target.files[0])} />
        </div>
        <button className="btn btn-primary" type="submit" disabled={status?.type === "loading"}>
          {status?.type === "loading" ? "Processing..." : "Upload & process"}
        </button>
      </form>
      {status && status.type !== "loading" && (
        <p className={status.type === "error" ? "error-text" : "muted"} style={{ marginTop: "0.8rem" }}>
          {status.message}
        </p>
      )}
    </div>
  );
}

function defaultValidUntil() {
  const d = new Date();
  d.setDate(d.getDate() + 7);
  return d.toISOString().split("T")[0];
}

const DEFAULT_DEADLINE_TIME = "23:59";

function formatDeadline(iso) {
  const d = new Date(iso);
  const date = d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
  const time = d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
  return `${date}, ${time}`;
}

function CreateExamCard({ onCreated }) {
  const [title, setTitle] = useState("");
  const [subject, setSubject] = useState("");
  const [accessCode, setAccessCode] = useState("");
  const [validUntil, setValidUntil] = useState(defaultValidUntil());
  const [deadlineTime, setDeadlineTime] = useState(DEFAULT_DEADLINE_TIME);
  const [questions, setQuestions] = useState([
    { question_text: "", total_marks: 10, rubric: "" },
  ]);
  const [status, setStatus] = useState(null);
  const [createdExam, setCreatedExam] = useState(null);

  const updateQuestion = (i, field, value) => {
    const next = [...questions];
    next[i] = { ...next[i], [field]: value };
    setQuestions(next);
  };

  const addQuestion = () =>
    setQuestions([...questions, { question_text: "", total_marks: 10, rubric: "" }]);

  const removeQuestion = (i) => setQuestions(questions.filter((_, idx) => idx !== i));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setStatus({ type: "loading" });
    setCreatedExam(null);
    try {
      const { data } = await teacherAPI.createExam({
        title,
        subject,
        access_code: accessCode,
        valid_until: validUntil
          ? new Date(`${validUntil}T${deadlineTime}`).toISOString()
          : undefined,
        questions: questions.map((q) => ({ ...q, total_marks: Number(q.total_marks) })),
      });
      setStatus({ type: "success", message: "Exam created — share the code below with your students." });
      setCreatedExam(data);
      setTitle(""); setSubject(""); setAccessCode("");
      setValidUntil(defaultValidUntil());
      setDeadlineTime(DEFAULT_DEADLINE_TIME);
      setQuestions([{ question_text: "", total_marks: 10, rubric: "" }]);
      onCreated?.();
    } catch (err) {
      const detail = err.response?.data;
      let message;
      if (detail) {
        if (typeof detail === "string") {
          message = detail;
        } else if (detail.detail) {
          message = detail.detail;
        } else {
          const parts = [];
          for (const [key, val] of Object.entries(detail)) {
            if (key === "questions" && Array.isArray(val)) {
              val.forEach((qErr, i) => {
                if (qErr && typeof qErr === "object") {
                  for (const [f, msgs] of Object.entries(qErr)) {
                    parts.push(`Question ${i + 1} ${f}: ${Array.isArray(msgs) ? msgs.join(", ") : msgs}`);
                  }
                }
              });
            } else {
              const msgs = Array.isArray(val) ? val : [val];
              parts.push(`${key}: ${msgs.join(", ")}`);
            }
          }
          message = parts.join(" | ") || "Could not create exam.";
        }
      } else {
        message = "Could not create exam. Check all fields are filled in.";
      }
      setStatus({ type: "error", message });
    }
  };

  return (
    <div className="card">
      <h3>Create exam</h3>
      <form onSubmit={handleSubmit}>
        <div className="field">
          <label htmlFor="title">Title</label>
          <input id="title" required value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Data Structures Midterm" />
        </div>
        <div className="field">
          <label htmlFor="exam-subject">Subject</label>
          <input id="exam-subject" required value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="e.g. Computer Science" />
        </div>

        <div style={{ display: "flex", gap: "0.75rem" }}>
          <div className="field" style={{ flex: 1 }}>
            <label htmlFor="access-code">Exam code (4 digits)</label>
            <input
              id="access-code" required maxLength={4} inputMode="numeric" pattern="\d{4}"
              placeholder="e.g. 4821"
              value={accessCode}
              onChange={(e) => setAccessCode(e.target.value.replace(/\D/g, "").slice(0, 4))}
            />
          </div>
          <div className="field" style={{ flex: 1 }}>
            <label htmlFor="valid-until">Due date</label>
            <input
              id="valid-until" type="date" required
              value={validUntil}
              onChange={(e) => setValidUntil(e.target.value)}
            />
          </div>
          <div className="field" style={{ flex: 1 }}>
            <label htmlFor="deadline-time">Due time</label>
            <input
              id="deadline-time" type="time" required
              value={deadlineTime}
              onChange={(e) => setDeadlineTime(e.target.value)}
            />
          </div>
        </div>
        <p className="muted" style={{ marginTop: "-0.5rem", fontSize: "0.78rem" }}>
          Students will use this 4-digit code to find the exam. The deadline defaults to 11:59 PM if no time is set.
        </p>

        <label>Questions</label>
        {questions.map((q, i) => (
          <div key={i} className="card" style={{ marginBottom: "0.75rem", background: "#fbf8f1" }}>
            <div className="field">
              <label>Question text</label>
              <textarea rows={8} required value={q.question_text}
                onChange={(e) => updateQuestion(i, "question_text", e.target.value)} />
            </div>
            <div style={{ display: "flex", gap: "0.75rem" }}>
              <div className="field" style={{ flex: 1 }}>
                <label>Total marks</label>
                <input type="number" min={1} required value={q.total_marks}
                  onChange={(e) => updateQuestion(i, "total_marks", e.target.value)} />
              </div>
              <div className="field" style={{ flex: 3 }}>
                <label>Rubric</label>
                <input required value={q.rubric} placeholder="e.g. Covers Big-O, trees, and graphs — 3 key areas, 5 marks each"
                  onChange={(e) => updateQuestion(i, "rubric", e.target.value)} />
              </div>
            </div>
            {questions.length > 1 && (
              <button type="button" className="btn btn-outline" onClick={() => removeQuestion(i)}>
                Remove question
              </button>
            )}
          </div>
        ))}
        <button type="button" className="btn btn-outline" onClick={addQuestion} style={{ marginBottom: "1rem" }}>
          + Add another question
        </button>

        <div>
          <button className="btn btn-primary" type="submit" disabled={status?.type === "loading"}>
            {status?.type === "loading" ? "Creating..." : "Create exam"}
          </button>
        </div>
      </form>

      {status?.message && (
        <p className={status.type === "error" ? "error-text" : "muted"} style={{ marginTop: "0.8rem" }}>
          {status.message}
        </p>
      )}

      {createdExam && (
        <div className="card" style={{ marginTop: "0.8rem", background: "#e3ede4" }}>
          <p style={{ margin: 0 }}>
            <strong>Exam code: {createdExam.access_code}</strong>
            {" · "}Due {formatDeadline(createdExam.valid_until)}
          </p>
          <p style={{ margin: "0.4em 0 0" }}>Question IDs:</p>
          <ul style={{ margin: "0.2em 0 0" }}>
            {createdExam.questions.map((q) => (
              <li key={q.id}>#{q.id} — {q.question_text.slice(0, 50)}{q.question_text.length > 50 ? "..." : ""}</li>
            ))}
          </ul>
          <p className="muted" style={{ fontSize: "0.8rem", marginBottom: 0 }}>
            Give students the exam code — they'll see this question list themselves.
          </p>
        </div>
      )}
    </div>
  );
}

function ExamsAndResults({ exams, onSelectExam, selectedExamId, submissions, onEditExam, onDeleteExam }) {
  const [expandedId, setExpandedId] = useState(null);
  const [expandedQuestionsId, setExpandedQuestionsId] = useState(null);
  const [visibleChunksResultId, setVisibleChunksResultId] = useState(null);
  const [questionChunksExamId, setQuestionChunksExamId] = useState(null);
  const [questionChunksQuestionId, setQuestionChunksQuestionId] = useState(null);
  const [questionChunksData, setQuestionChunksData] = useState(null);
  const [questionChunksLoading, setQuestionChunksLoading] = useState(false);

  const toggle = (id) => setExpandedId(expandedId === id ? null : id);
  const toggleQuestions = (id) => setExpandedQuestionsId(expandedQuestionsId === id ? null : id);
  const toggleChunks = (id) => setVisibleChunksResultId(visibleChunksResultId === id ? null : id);

  const loadQuestionChunks = async (examId, questionId) => {
    if (questionChunksExamId === examId && questionChunksQuestionId === questionId) {
      setQuestionChunksExamId(null);
      setQuestionChunksQuestionId(null);
      setQuestionChunksData(null);
      return;
    }
    setQuestionChunksExamId(examId);
    setQuestionChunksQuestionId(questionId);
    setQuestionChunksLoading(true);
    setQuestionChunksData(null);
    try {
      const { data } = await teacherAPI.questionChunks(examId, questionId);
      setQuestionChunksData(data);
    } catch {
      setQuestionChunksData({ chunks: [], error: "Failed to load chunks." });
    } finally {
      setQuestionChunksLoading(false);
    }
  };

  return (
    <div className="card">
      <h3>Your exams</h3>
      {exams.length === 0 && <p className="muted">No exams yet — create one above.</p>}
      <table>
        <thead>
          <tr><th>ID</th><th>Exam code</th><th>Title</th><th>Subject</th><th>Created</th><th></th></tr>
        </thead>
        <tbody>
          {exams.map((exam) => (
            <tr key={exam.id}>
              <td><strong>{exam.id}</strong></td>
              <td><code>{exam.access_code}</code></td>
              <td>{exam.title}</td>
              <td>{exam.subject}</td>
              <td>{new Date(exam.created_at).toLocaleDateString()}</td>
              <td>
                <button className="btn btn-outline" onClick={() => toggleQuestions(exam.id)}>
                  {expandedQuestionsId === exam.id ? "Hide questions" : "View questions"}
                </button>{" "}
                <button className="btn btn-outline" onClick={() => onSelectExam(exam.id)}>
                  View results
                </button>{" "}
                <button className="btn btn-outline" onClick={() => onEditExam(exam)}>
                  Edit
                </button>{" "}
                <button className="btn btn-outline" onClick={() => onDeleteExam(exam)}>
                  Delete
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {expandedQuestionsId && (
        (() => {
          const exam = exams.find((e) => e.id === expandedQuestionsId);
          if (!exam || !exam.questions?.length) return <p className="muted" style={{ marginTop: "1rem" }}>No questions for this exam.</p>;
          return (
            <div style={{ marginTop: "1rem" }}>
              <h4 style={{ margin: "0 0 0.75rem" }}>Questions for "{exam.title}"</h4>
              {exam.questions.map((q, i) => (
                <div key={q.id ?? i} className="card" style={{ marginBottom: "0.75rem", background: "#fbf8f1" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.4rem" }}>
                    <strong>Question {i + 1} <span className="muted" style={{ fontWeight: 400 }}>(ID #{q.id})</span></strong>
                    <span>{q.total_marks} marks</span>
                  </div>
                  <p style={{ margin: "0 0 0.4rem", whiteSpace: "pre-wrap" }}>{q.question_text}</p>
                  <p className="muted" style={{ margin: 0, fontSize: "0.82rem" }}><strong>Rubric:</strong> {q.rubric}</p>
                  <div style={{ marginTop: "0.6rem" }}>
                    <button
                      className="btn btn-outline"
                      style={{ fontSize: "0.8rem", padding: "0.25em 0.7em" }}
                      onClick={() => loadQuestionChunks(exam.id, q.id)}
                    >
                      {questionChunksExamId === exam.id && questionChunksQuestionId === q.id ? "Hide relevant chunks" : "View relevant chunks"}
                    </button>
                    {questionChunksExamId === exam.id && questionChunksQuestionId === q.id && (
                      <div style={{ marginTop: "0.5rem", padding: "0.65rem", background: "#eef4ff", border: "1px solid #c5d5f5", borderRadius: "var(--radius)" }}>
                        {questionChunksLoading && <p className="muted" style={{ margin: 0, fontSize: "0.82rem" }}>Loading chunks...</p>}
                        {!questionChunksLoading && questionChunksData && (
                          <>
                            {questionChunksData.error ? (
                              <p className="muted" style={{ margin: 0, fontSize: "0.82rem" }}>{questionChunksData.error}</p>
                            ) : (
                              <>
                                <p className="muted" style={{ margin: "0 0 0.4rem", fontSize: "0.78rem" }}>
                                  <strong>Source:</strong> Extracted from your uploaded PDF · {questionChunksData.num_chunks} relevant chunk{questionChunksData.num_chunks !== 1 ? "s" : ""} · Best similarity: {(questionChunksData.similarity_score * 100).toFixed(1)}%
                                </p>
                                {questionChunksData.chunks?.length > 0 ? (
                                  questionChunksData.chunks.map((chunk, ci) => (
                                    <div key={ci} className="card" style={{ marginBottom: "0.5rem", background: "#fbf8f1" }}>
                                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", margin: "0 0 0.3em" }}>
                                        <p className="muted" style={{ margin: 0, fontSize: "0.75rem" }}>
                                          Chunk {chunk.chunk_index ?? ci}
                                        </p>
                                        <span style={{
                                          fontSize: "0.7rem",
                                          padding: "0.15em 0.5em",
                                          borderRadius: "4px",
                                          background: chunk.overlap_pct === 0 ? "#e8f5e9" : "#fff3e0",
                                          color: chunk.overlap_pct === 0 ? "#2e7d32" : "#e65100",
                                          fontWeight: 600,
                                        }}>
                                          {chunk.overlap_pct === 0 ? "New paragraph" : `${chunk.overlap_pct}% overlap`}
                                        </span>
                                      </div>
                                      <p style={{ margin: 0, fontSize: "0.88rem" }}>{chunk.text}</p>
                                    </div>
                                  ))
                                ) : (
                                  <p className="muted" style={{ margin: 0, fontSize: "0.82rem" }}>No relevant chunks found for this question.</p>
                                )}
                              </>
                            )}
                          </>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          );
        })()
      )}

      {selectedExamId && (() => {
        const selectedExam = exams.find((e) => e.id === selectedExamId);
        const questionMap = {};
        if (selectedExam?.questions) {
          selectedExam.questions.forEach((q) => { questionMap[q.id] = q.question_text; });
        }
        return (
          <div style={{ marginTop: "1.5rem" }}>
            <h3>Submissions for exam #{selectedExamId}</h3>
            {submissions.length === 0 && <p className="muted">No submissions yet.</p>}
            {submissions.map((sub) => (
              <div key={sub.id} className="card" style={{ marginBottom: "0.75rem", background: "#fbf8f1" }}>
                <div
                  onClick={() => toggle(sub.id)}
                  style={{ cursor: "pointer", display: "flex", justifyContent: "space-between", alignItems: "center" }}
                >
                  <div>
                    <strong>{sub.student_name || "Unknown"}</strong>
                    {sub.student_roll && <span className="muted" style={{ marginLeft: "0.5rem" }}>({sub.student_roll})</span>}
                    <span className={`badge ${sub.status === "flagged" ? "badge-flagged" : sub.status === "graded" ? "badge-graded" : "badge-pending"}`} style={{ marginLeft: "0.75rem" }}>
                      {sub.status}
                    </span>
                    <span className="muted" style={{ marginLeft: "0.75rem", fontSize: "0.82rem" }}>
                      {sub.results.length} question{sub.results.length !== 1 ? "s" : ""}
                    </span>
                  </div>
                  <span style={{ fontSize: "0.85rem", color: "#888", userSelect: "none" }}>
                    {expandedId === sub.id ? "▲ Hide" : "▼ Show"}
                  </span>
                </div>

                {expandedId === sub.id && (
                  <div style={{ marginTop: "0.75rem" }}>
                    {sub.results.map((r) => (
                      <div key={r.id} style={{ borderTop: "1px solid var(--paper-line)", padding: "0.75rem 0" }}>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "0.4rem" }}>
                          <div style={{ flex: 1, minWidth: 0 }}>
                            <span className="muted" style={{ fontSize: "0.78rem" }}>Q{r.question}:</span>{" "}
                            <strong style={{ whiteSpace: "pre-wrap" }}>{questionMap[r.question] || `Question #${r.question}`}</strong>
                            {r.created_at && (
                              <span className="muted" style={{ marginLeft: "0.6rem", fontSize: "0.75rem" }}>
                                Uploaded: {new Date(r.created_at).toLocaleString(undefined, {
                                  year: "numeric", month: "short", day: "numeric",
                                  hour: "numeric", minute: "2-digit",
                                })}
                              </span>
                            )}
                          </div>
                          <span style={{ marginLeft: "0.75rem", whiteSpace: "nowrap" }}>
                            <strong>{r.marks_awarded ?? "—"}</strong> / {r.total_marks}
                            {r.flagged && (
                              <span className="badge badge-flagged" style={{ marginLeft: "0.5rem" }}>
                                {r.flag_reason?.replaceAll("_", " ")}
                              </span>
                            )}
                          </span>
                        </div>
                        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.5rem", fontSize: "0.85rem" }}>
                          <div>
                            <span className="muted">OCR confidence:</span>{" "}
                            {r.ocr_confidence != null ? `${r.ocr_confidence.toFixed(1)}%` : "—"}
                          </div>

                        </div>
                        {r.ocr_cleaned_text && (
                          <details style={{ marginTop: "0.5rem" }}>
                            <summary style={{ cursor: "pointer", fontSize: "0.82rem", color: "var(--ink-blue)" }}>
                              OCR extracted text
                            </summary>
                            <pre style={{ margin: "0.4rem 0 0", padding: "0.6rem", background: "#fff", border: "1px solid var(--paper-line)", borderRadius: "var(--radius)", fontSize: "0.8rem", whiteSpace: "pre-wrap", maxHeight: "8em", overflow: "auto" }}>
                              {r.ocr_cleaned_text}
                            </pre>
                          </details>
                        )}
                        <div style={{ marginTop: "0.5rem" }}>
                          <button
                            className="btn btn-outline"
                            style={{ fontSize: "0.8rem", padding: "0.25em 0.7em" }}
                            onClick={() => toggleChunks(r.id)}
                          >
                            {visibleChunksResultId === r.id ? "Hide extracted chunks" : "View extracted chunks"}
                          </button>
                          {r.retrieved_chunks?.length > 0 && (
                            <span className="muted" style={{ marginLeft: "0.4rem", fontSize: "0.75rem" }}>
                              ({r.retrieved_chunks.length} chunk{r.retrieved_chunks.length > 1 ? "s" : ""} from your PDF)
                            </span>
                          )}
                          {visibleChunksResultId === r.id && (
                            <div style={{ marginTop: "0.5rem", maxHeight: "16em", overflow: "auto", padding: "0.65rem", background: "#eef4ff", border: "1px solid #c5d5f5", borderRadius: "var(--radius)" }}>
                              <p className="muted" style={{ margin: "0 0 0.5rem", fontSize: "0.75rem", fontWeight: 600 }}>
                                Extracted from your uploaded reference PDF (not AI-generated)
                              </p>
                              {r.retrieved_chunks?.length > 0 ? (
                                r.retrieved_chunks.map((chunk, i) => {
                                  const text = typeof chunk === "string" ? chunk : chunk.text || JSON.stringify(chunk);
                                  const chunkIndex = typeof chunk === "object" && chunk.chunk_index != null ? chunk.chunk_index : i;
                                  const overlapPct = typeof chunk === "object" && chunk.overlap_pct != null ? chunk.overlap_pct : 0;
                                  return (
                                    <div key={i} className="card" style={{ marginBottom: "0.5rem", background: "#fbf8f1" }}>
                                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", margin: "0 0 0.3em" }}>
                                        <p className="muted" style={{ margin: 0, fontSize: "0.75rem" }}>
                                          Chunk {chunkIndex}
                                        </p>
                                        <span style={{
                                          fontSize: "0.7rem",
                                          padding: "0.15em 0.5em",
                                          borderRadius: "4px",
                                          background: overlapPct === 0 ? "#e8f5e9" : "#fff3e0",
                                          color: overlapPct === 0 ? "#2e7d32" : "#e65100",
                                          fontWeight: 600,
                                        }}>
                                          {overlapPct === 0 ? "New paragraph" : `${overlapPct}% overlap`}
                                        </span>
                                      </div>
                                      <p style={{ margin: 0, fontSize: "0.88rem" }}>{text}</p>
                                    </div>
                                  );
                                })
                              ) : (
                                <p className="muted" style={{ margin: 0, fontSize: "0.82rem" }}>
                                  No relevant reference chunks were retrieved for this answer.
                                </p>
                              )}
                            </div>
                          )}
                        </div>
                        {r.feedback && (
                          <div style={{ marginTop: "0.5rem", padding: "0.5rem", background: "#fff", border: "1px solid var(--paper-line)", borderRadius: "var(--radius)", fontSize: "0.85rem" }}>
                            <strong style={{ fontSize: "0.78rem", color: "var(--ink-soft)" }}>Feedback:</strong>
                            <p style={{ margin: "0.25rem 0 0" }}>{r.feedback}</p>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        );
      })()}
    </div>
  );
}

function TeacherOverrideForm({ item, onDone, onClose }) {
  const [marks, setMarks] = useState("");
  const [feedback, setFeedback] = useState("");
  const [status, setStatus] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setStatus({ type: "loading" });
    try {
      await teacherAPI.reviewOverride(item.result.id, {
        override_marks: Number(marks),
        override_feedback: feedback,
      });
      setStatus({ type: "success" });
      onDone();
    } catch (err) {
      setStatus({
        type: "error",
        message: err.response?.data?.detail || "Could not save override. Check the marks are in range.",
      });
    }
  };

  return (
    <form onSubmit={handleSubmit} style={{ marginTop: "0.8rem", borderTop: "1px solid var(--paper-line)", paddingTop: "0.75rem" }}>
      <div className="field">
        <label>Marks (0–{item.result.total_marks})</label>
        <input type="number" step="0.5" min={0} max={item.result.total_marks} required
          value={marks} onChange={(e) => setMarks(e.target.value)} />
      </div>
      <div className="field">
        <label>Feedback</label>
        <textarea rows={3} required value={feedback} onChange={(e) => setFeedback(e.target.value)} />
      </div>
      <div style={{ display: "flex", gap: "0.75rem", alignItems: "center" }}>
        <button className="btn btn-primary" type="submit" disabled={status?.type === "loading"}>
          {status?.type === "loading" ? "Saving..." : "Review & save"}
        </button>
        <button className="btn btn-outline" type="button" onClick={onClose}>Close</button>
        {status?.type === "error" && status.message && <span className="error-text">{status.message}</span>}
      </div>
    </form>
  );
}

function ReviewQueueCard({ queue, onReviewed }) {
  const [expandedId, setExpandedId] = useState(null);

  const toggle = (id) => setExpandedId(expandedId === id ? null : id);

  return (
    <div className="card">
      <h3>Flagged answers pending review</h3>
      {queue.length === 0 && <p className="muted">Nothing flagged right now.</p>}
      {queue.map((item) => (
        <div key={item.id} className="card" style={{ marginBottom: "0.75rem", background: "#fbf8f1" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: "0.5rem" }}>
            <span className="badge badge-flagged">{item.reason.replaceAll("_", " ")}</span>
            <span className="muted" style={{ fontSize: "0.8rem", whiteSpace: "nowrap" }}>Result #{item.result.id}</span>
          </div>

          <p style={{ margin: "0.6rem 0 0.2rem" }}>
            <strong>{item.student_name || "Unknown"}</strong>
            {item.student_roll && <span className="muted" style={{ marginLeft: "0.5rem" }}>({item.student_roll})</span>}
            {item.exam_title && <span className="muted" style={{ marginLeft: "0.5rem" }}>· {item.exam_title}</span>}
          </p>
          <p className="muted" style={{ margin: "0 0 0.5rem", fontSize: "0.85rem", whiteSpace: "pre-wrap" }}>
            <strong>Q:</strong> {item.question_text || `Question #${item.result.question}`}
          </p>

          <p style={{ marginBottom: "0.3em" }}><strong>OCR text:</strong> {item.result.ocr_cleaned_text || "(none)"}</p>
          {Array.isArray(item.result.answer_sheet) && item.result.answer_sheet.length > 0 && (
            <p style={{ marginBottom: "0.3em", display: "flex", gap: "0.4rem", flexWrap: "wrap" }}>
              {item.result.answer_sheet.map((path, idx) => (
                <a
                  key={idx}
                  className="btn btn-outline"
                  href={path.startsWith("http") ? path : `${MEDIA_ORIGIN}/media/${path}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ fontSize: "0.85rem" }}
                >
                  View image {item.result.answer_sheet.length > 1 ? idx + 1 : ""}
                </a>
              ))}
            </p>
          )}
          <p className="muted" style={{ margin: 0 }}>
            Confidence: {item.result.ocr_confidence?.toFixed(1) ?? "—"}%
            {" · "}Marks so far: {item.result.marks_awarded ?? "—"} / {item.result.total_marks}
          </p>

          {expandedId !== item.id ? (
            <button className="btn btn-outline" style={{ marginTop: "0.6rem" }} onClick={() => toggle(item.id)}>
              Review & override
            </button>
          ) : (
            <TeacherOverrideForm item={item} onDone={onReviewed} onClose={() => toggle(item.id)} />
          )}
        </div>
      ))}
    </div>
  );
}

export default function TeacherDashboard() {
  const [exams, setExams] = useState([]);
  const [selectedExamId, setSelectedExamId] = useState(null);
  const [submissions, setSubmissions] = useState([]);
  const [queue, setQueue] = useState([]);
  const [editingExam, setEditingExam] = useState(null);

  const loadExams = async () => {
    try {
      const { data } = await teacherAPI.listExams();
      setExams(data);
    } catch {
      setExams([]);
    }
  };

  const loadQueue = async () => {
    try {
      const { data } = await teacherAPI.reviewQueue();
      setQueue(data);
    } catch {
      setQueue([]);
    }
  };

  useEffect(() => {
    loadExams();
    loadQueue();
  }, []);

  const handleSelectExam = async (examId) => {
    setSelectedExamId(examId);
    try {
      const { data } = await teacherAPI.examSubmissions(examId);
      setSubmissions(data);
    } catch {
      setSubmissions([]);
    }
  };

  const handleExamSaved = async () => {
    setEditingExam(null);
    await loadExams();
  };

  const handleDeleteExam = async (exam) => {
    if (!window.confirm(`Delete exam "${exam.title}" (ID ${exam.id}) and all of its submissions and results? This cannot be undone.`)) {
      return;
    }
    try {
      await teacherAPI.deleteExam(exam.id);
      if (selectedExamId === exam.id) setSelectedExamId(null);
      if (editingExam?.id === exam.id) setEditingExam(null);
      await loadExams();
    } catch {
      window.alert("Could not delete the exam. Please try again.");
    }
  };

  return (
    <div style={{ display: "grid", gap: "1.5rem" }}>
      <VisionStatusBadge />
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1.5rem" }}>
        <UploadMaterialCard />
        <CreateExamCard onCreated={loadExams} />
      </div>
      <MaterialsList />
      {editingExam && (
        <EditExamCard
          exam={editingExam}
          onSaved={handleExamSaved}
          onClose={() => setEditingExam(null)}
        />
      )}
      <ExamsAndResults
        exams={exams}
        onSelectExam={handleSelectExam}
        onEditExam={setEditingExam}
        onDeleteExam={handleDeleteExam}
        selectedExamId={selectedExamId}
        submissions={submissions}
      />
      <ReviewQueueCard queue={queue} onReviewed={loadQueue} />
    </div>
  );
}