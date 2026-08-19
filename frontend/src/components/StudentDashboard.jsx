import { useState } from "react";
import { studentAPI } from "../services/api";
import ResultViewer from "./ResultViewer";

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
            Valid until {new Date(exam.valid_until).toLocaleDateString()}
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
  const [imageFile, setImageFile] = useState(null);
  const [status, setStatus] = useState(null);
  const [submissionResult, setSubmissionResult] = useState(null);

  const [lookupExamId, setLookupExamId] = useState("");
  const [lookupResults, setLookupResults] = useState(null);
  const [lookupError, setLookupError] = useState("");

  const handlePickQuestion = (pickedExamId, pickedQuestionId) => {
    setExamId(String(pickedExamId));
    setQuestionId(String(pickedQuestionId));
    setStatus(null);
    setSubmissionResult(null);
    document.getElementById("submit-answer-form")?.scrollIntoView({ behavior: "smooth" });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!imageFile) return;
    setStatus({ type: "loading", message: "Grading in progress — this runs OCR and AI grading, may take a moment..." });
    setSubmissionResult(null);

    const formData = new FormData();
    formData.append("exam_id", examId);
    formData.append("question_id", questionId);
    formData.append("image_file", imageFile);

    try {
      const { data } = await studentAPI.submitAnswer(formData);
      setSubmissionResult(data.result);
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
            <label htmlFor="image_file">Answer sheet photo</label>
            <input id="image_file" type="file" accept="image/*" required
              onChange={(e) => setImageFile(e.target.files[0])} />
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
            <label htmlFor="lookup_exam_id">Exam ID</label>
            <input id="lookup_exam_id" type="number" required value={lookupExamId}
              onChange={(e) => setLookupExamId(e.target.value)} />
          </div>
          <button className="btn btn-outline" type="submit">Look up</button>
        </form>

        {lookupError && <p className="error-text">{lookupError}</p>}

        {lookupResults && (
          <div style={{ marginTop: "1rem" }}>
            <p className="muted">
              Submission status: <span className={`badge badge-${lookupResults.status}`}>{lookupResults.status}</span>
            </p>
            {lookupResults.results.map((r) => (
              <div key={r.id} style={{ marginBottom: "1rem" }}>
                <ResultViewer result={r} />
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}