import { useState } from "react";
import { studentAPI } from "../services/api";
import ResultViewer from "./ResultViewer";

const MEDIA_ORIGIN = new URL(import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000/api").origin;

function formatDeadline(iso) {
  const d = new Date(iso);
  const date = d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
  const time = d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
  return `${date}, ${time}`;
}

function QuestionBrowser({ onPick }) {
  const [code, setCode] = useState("");
  const [exam, setExam] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleLookup = async (e) => {
    e.preventDefault();
    setError("");
    setExam(null);
    setLoading(true);
    try {
      const { data } = await studentAPI.examLookupByCode(code);
      setExam(data);
    } catch (err) {
      setError(err.response?.data?.detail || "Could not find that exam.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="card">
      <h3>Find an exam</h3>
      <p className="muted" style={{ marginTop: 0 }}>
        Enter the 4-digit exam code your teacher gave you.
      </p>
      <form onSubmit={handleLookup} style={{ display: "flex", gap: "0.75rem", alignItems: "flex-end" }}>
        <div className="field" style={{ flex: 1, marginBottom: 0 }}>
          <label htmlFor="exam_code">Exam code</label>
          <input
            id="exam_code" required maxLength={4} inputMode="numeric" pattern="\d{4}"
            placeholder="e.g. 4821"
            value={code}
            onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 4))}
          />
        </div>
        <button className="btn btn-outline" type="submit" disabled={loading}>
          {loading ? "Looking up..." : "Find questions"}
        </button>
      </form>

      {error && <p className="error-text">{error}</p>}

      {exam && (
        <div style={{ marginTop: "1rem" }}>
          <h3 style={{ marginBottom: "0.4rem" }}>
            {exam.title} <span className="muted" style={{ fontWeight: 400, fontSize: "0.8rem" }}>({exam.subject})</span>
          </h3>
          <p className="muted" style={{ fontSize: "0.8rem", marginTop: 0 }}>
            Teacher: <strong style={{ color: "var(--ink-blue)" }}>{exam.teacher_name || "Unknown"}</strong>
          </p>
          <p className="muted" style={{ fontSize: "0.8rem", marginTop: 0 }}>
            Due {formatDeadline(exam.valid_until)}
          </p>
          {exam.questions.length === 0 && <p className="muted">No questions on this exam yet.</p>}
          <table>
            <thead>
              <tr><th>ID</th><th>Question</th><th>Marks</th><th></th></tr>
            </thead>
            <tbody>
              {exam.questions.map((q) => (
                <tr key={q.id}>
                  <td>{q.id}</td>
                  <td>{q.question_text}</td>
                  <td>{q.total_marks}</td>
                  <td>
                    <button className="btn btn-outline" type="button" onClick={() => onPick(exam.id, q.id)}>
                      Answer this
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default function StudentDashboard() {
  const [examId, setExamId] = useState("");
  const [questionId, setQuestionId] = useState("");
  const [imageFiles, setImageFiles] = useState([]);
  const [status, setStatus] = useState(null);
  const [submissionResult, setSubmissionResult] = useState(null);

  const [lookupExamId, setLookupExamId] = useState("");
  const [lookupResults, setLookupResults] = useState(null);
  const [lookupError, setLookupError] = useState("");
  const [deletingId, setDeletingId] = useState(null);

  const handlePickQuestion = (pickedExamId, pickedQuestionId) => {
    setExamId(String(pickedExamId));
    setQuestionId(String(pickedQuestionId));
    setStatus(null);
    setSubmissionResult(null);
    document.getElementById("submit-answer-form")?.scrollIntoView({ behavior: "smooth" });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!imageFiles.length) return;
    setStatus({ type: "loading", message: "Grading in progress — this runs OCR and AI grading, may take a moment..." });
    setSubmissionResult(null);

    const formData = new FormData();
    formData.append("exam_id", examId);
    formData.append("question_id", questionId);
    for (const file of imageFiles) {
      formData.append("image_file", file);
    }

    try {
      const { data } = await studentAPI.submitAnswer(formData);
      setSubmissionResult(data.result);
      setImageFiles([]);
      setStatus({ type: "success", message: "Submitted and graded." });
    } catch (err) {
      setStatus({
        type: "error",
        message: err.response?.data?.error || err.response?.data?.detail || "Submission failed.",
      });
    }
  };

  const handleLookup = async (e) => {
    e.preventDefault();
    setLookupError("");
    setLookupResults(null);
    try {
      const { data } = await studentAPI.examResults(lookupExamId);
      setLookupResults(data);
    } catch (err) {
      setLookupError(err.response?.data?.detail || "No results found for that exam yet.");
    }
  };

  const canEditResults =
    lookupResults?.valid_until && new Date(lookupResults.valid_until) > new Date();

  const handleDeleteResult = async (result) => {
    if (!window.confirm("Delete this uploaded answer sheet? You can upload a new one before the deadline.")) {
      return;
    }
    setDeletingId(result.id);
    setLookupError("");
    try {
      await studentAPI.deleteResult(result.id);
      // Pre-fill the submit form so the student can re-upload right away.
      setExamId(String(lookupResults.exam));
      setQuestionId(String(result.question));
      setStatus(null);
      setSubmissionResult(null);
      const { data } = await studentAPI.examResults(lookupExamId);
      setLookupResults(data);
      document.getElementById("submit-answer-form")?.scrollIntoView({ behavior: "smooth" });
    } catch (err) {
      setLookupError(err.response?.data?.detail || "Could not delete the answer sheet.");
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div style={{ display: "grid", gap: "1.5rem" }}>
      <QuestionBrowser onPick={handlePickQuestion} />

      <div className="card" id="submit-answer-form">
        <h3>Submit an answer</h3>
        <p className="muted" style={{ marginTop: 0 }}>
          Upload a photo of your handwritten answer sheet for a question.
        </p>
        <form onSubmit={handleSubmit}>
          <div style={{ display: "flex", gap: "0.75rem" }}>
            <div className="field" style={{ flex: 1 }}>
              <label htmlFor="exam_id">Exam ID</label>
              <input id="exam_id" type="number" required value={examId} onChange={(e) => setExamId(e.target.value)} />
            </div>
            <div className="field" style={{ flex: 1 }}>
              <label htmlFor="question_id">Question ID</label>
              <input id="question_id" type="number" required value={questionId} onChange={(e) => setQuestionId(e.target.value)} />
            </div>
          </div>
          <div className="field">
            <label>Answer sheet photo(s)</label>
            <label
              htmlFor="image_file"
              className="btn btn-outline"
              style={{ display: "inline-flex", alignItems: "center", gap: "0.4rem", cursor: "pointer", marginBottom: "0.4rem" }}
            >
              {imageFiles.length === 0
                ? "Choose files"
                : `${imageFiles.length} file${imageFiles.length > 1 ? "s" : ""} chosen`}
            </label>
            <input id="image_file" type="file" accept="image/*" multiple style={{ display: "none" }}
              onChange={(e) => {
                const newFiles = Array.from(e.target.files);
                setImageFiles((prev) => {
                  const existingNames = new Set(prev.map((f) => f.name));
                  const unique = newFiles.filter((f) => !existingNames.has(f.name));
                  return [...prev, ...unique];
                });
                e.target.value = "";
              }} />
            {imageFiles.length > 0 && (
              <ul className="muted" style={{ margin: "0.3rem 0 0", fontSize: "0.85rem", paddingLeft: "1.2rem" }}>
                {imageFiles.map((f, i) => (
                  <li key={i} style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
                    {f.name}
                    <button type="button" style={{ background: "none", border: "none", color: "#c0392b", cursor: "pointer", fontSize: "0.8rem" }}
                      onClick={() => setImageFiles((prev) => prev.filter((_, j) => j !== i))}>
                      remove
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <button className="btn btn-primary" type="submit" disabled={status?.type === "loading"}>
            {status?.type === "loading" ? "Grading..." : "Submit answer"}
          </button>
        </form>
        {status && status.type !== "loading" && (
          <p className={status.type === "error" ? "error-text" : "muted"} style={{ marginTop: "0.8rem" }}>
            {status.message}
          </p>
        )}
      </div>

      {submissionResult && (
        <div className="card">
          <h3>Your result</h3>
          <ResultViewer result={submissionResult} />
        </div>
      )}

      <div className="card">
        <h3>View past results</h3>
        <form onSubmit={handleLookup} style={{ display: "flex", gap: "0.75rem", alignItems: "flex-end" }}>
          <div className="field" style={{ flex: 1, marginBottom: 0 }}>
            <label htmlFor="lookup_exam_id">Exam code or ID</label>
            <input id="lookup_exam_id" type="number" required value={lookupExamId}
              onChange={(e) => setLookupExamId(e.target.value)} placeholder="e.g. 1111" />
          </div>
          <button className="btn btn-outline" type="submit">Look up</button>
        </form>

        {lookupError && <p className="error-text">{lookupError}</p>}

{lookupResults && (
        <div style={{ marginTop: "1rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
            <p className="muted" style={{ margin: 0 }}>
              Submission status: <span className={`badge badge-${lookupResults.status}`}>{lookupResults.status}</span>
              {lookupResults.valid_until && (
                <> · Due: {formatDeadline(lookupResults.valid_until)}</>
              )}
            </p>
            <button className="btn btn-outline" type="button" onClick={() => setLookupResults(null)}>
              Close
            </button>
          </div>
          {!canEditResults && (
            <p className="muted" style={{ marginTop: 0 }}>
              This exam has closed — answers can no longer be edited or resubmitted.
            </p>
          )}
          {lookupResults.results.length === 0 && (
            <p className="muted">No answer sheets uploaded for this exam yet.</p>
          )}
          {lookupResults.results.map((r) => (
            <div key={r.id} style={{ marginBottom: "1rem" }}>
              <ResultViewer result={r} />
              {canEditResults && (
                <div style={{ marginTop: "0.5rem", display: "flex", alignItems: "center", gap: "0.5rem", flexWrap: "wrap" }}>
                  {Array.isArray(r.answer_sheet) && r.answer_sheet.length > 0 && r.answer_sheet.map((path, idx) => (
                    <a key={idx} className="btn btn-outline" href={`${MEDIA_ORIGIN}/media/${path}`} target="_blank" rel="noreferrer">
                      View image {r.answer_sheet.length > 1 ? idx + 1 : ""}
                    </a>
                  ))}
                  {!Array.isArray(r.answer_sheet) && r.answer_sheet && (
                    <a className="btn btn-outline" href={`${MEDIA_ORIGIN}/media/${r.answer_sheet}`} target="_blank" rel="noreferrer">
                      View uploaded sheet
                    </a>
                  )}
                  <button
                    className="btn btn-outline"
                    type="button"
                    disabled={deletingId === r.id}
                    onClick={() => handleDeleteResult(r)}
                  >
                    {deletingId === r.id ? "Deleting..." : "Delete & resubmit"}
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
      </div>
    </div>
  );
}