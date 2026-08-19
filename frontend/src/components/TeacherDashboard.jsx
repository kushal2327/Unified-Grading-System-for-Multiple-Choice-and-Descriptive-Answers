import { useEffect, useState } from "react";
import { teacherAPI } from "../services/api";
import MaterialsList from "./MaterialsList";

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

function CreateExamCard({ onCreated }) {
  const [title, setTitle] = useState("");
  const [subject, setSubject] = useState("");
  const [accessCode, setAccessCode] = useState("");
  const [validUntil, setValidUntil] = useState(defaultValidUntil());
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
        valid_until: validUntil ? new Date(validUntil).toISOString() : undefined,
        questions: questions.map((q) => ({ ...q, total_marks: Number(q.total_marks) })),
      });
      setStatus({ type: "success", message: "Exam created — share the code below with your students." });
      setCreatedExam(data);
      setTitle(""); setSubject(""); setAccessCode("");
      setValidUntil(defaultValidUntil());
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
            <label htmlFor="valid-until">Valid until</label>
            <input
              id="valid-until" type="date" required
              value={validUntil}
              onChange={(e) => setValidUntil(e.target.value)}
            />
          </div>
        </div>
        <p className="muted" style={{ marginTop: "-0.5rem", fontSize: "0.78rem" }}>
          Students will use this 4-digit code to find the exam. Defaults to 1 week from today.
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
            {" · "}Valid until {new Date(createdExam.valid_until).toLocaleDateString()}
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

function ExamsAndResults({ exams, onSelectExam, selectedExamId, submissions }) {
  const [expandedId, setExpandedId] = useState(null);

  const toggle = (id) => setExpandedId(expandedId === id ? null : id);

  return (
    <div className="card">
      <h3>Your exams</h3>
      {exams.length === 0 && <p className="muted">No exams yet — create one above.</p>}
      <table>
        <thead>
          <tr><th>ID</th><th>Title</th><th>Subject</th><th>Created</th><th></th></tr>
        </thead>
        <tbody>
          {exams.map((exam) => (
            <tr key={exam.id}>
              <td><strong>{exam.id}</strong></td>
              <td>{exam.title}</td>
              <td>{exam.subject}</td>
              <td>{new Date(exam.created_at).toLocaleDateString()}</td>
              <td>
                <button className="btn btn-outline" onClick={() => onSelectExam(exam.id)}>
                  View results
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {selectedExamId && (
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
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.4rem" }}>
                        <strong>Q{r.question}</strong>
                        <span>
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
                        <div>
                          <span className="muted">Similarity:</span>{" "}
                          {r.similarity_score != null ? r.similarity_score.toFixed(2) : "—"}
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
      )}
    </div>
  );
}

function ReviewQueueCard({ queue }) {
  return (
    <div className="card">
      <h3>Flagged answers pending review</h3>
      {queue.length === 0 && <p className="muted">Nothing flagged right now.</p>}
      {queue.map((item) => (
        <div key={item.id} className="card" style={{ marginBottom: "0.75rem", background: "#fbf8f1" }}>
          <span className="badge badge-flagged">{item.reason.replaceAll("_", " ")}</span>
          <p style={{ marginBottom: "0.3em" }}><strong>OCR text:</strong> {item.result.ocr_cleaned_text || "(none)"}</p>
          <p className="muted" style={{ margin: 0 }}>
            Confidence: {item.result.ocr_confidence?.toFixed(1)}% · Similarity: {item.result.similarity_score?.toFixed(2) ?? "n/a"}
          </p>
        </div>
      ))}
      <p className="muted" style={{ fontSize: "0.82rem" }}>
        Overriding marks/feedback on a flagged answer is done from the Admin dashboard.
      </p>
    </div>
  );
}

export default function TeacherDashboard() {
  const [exams, setExams] = useState([]);
  const [selectedExamId, setSelectedExamId] = useState(null);
  const [submissions, setSubmissions] = useState([]);
  const [queue, setQueue] = useState([]);

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

  return (
    <div style={{ display: "grid", gap: "1.5rem" }}>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1.5rem" }}>
        <UploadMaterialCard />
        <CreateExamCard onCreated={loadExams} />
      </div>
      <MaterialsList />
      <ExamsAndResults
        exams={exams}
        onSelectExam={handleSelectExam}
        selectedExamId={selectedExamId}
        submissions={submissions}
      />
      <ReviewQueueCard queue={queue} />
    </div>
  );
}