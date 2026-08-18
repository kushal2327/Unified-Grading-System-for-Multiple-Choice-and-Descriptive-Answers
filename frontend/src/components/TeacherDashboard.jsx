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
          <input id="subject" required value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="e.g. Biology" />
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

function CreateExamCard({ onCreated }) {
  const [title, setTitle] = useState("");
  const [subject, setSubject] = useState("");
  const [questions, setQuestions] = useState([
    { question_text: "", total_marks: 10, rubric: "" },
  ]);
  const [status, setStatus] = useState(null);

  const updateQuestion = (i, field, value) => {
    const next = [...questions];
    next[i] = { ...next[i], [field]: value };
    setQuestions(next);
  };

  const addQuestion = () =>
    setQuestions([...questions, { question_text: "", total_marks: 10, rubric: "" }]);

  const removeQuestion = (i) => setQuestions(questions.filter((_, idx) => idx !== i));

  const [createdExam, setCreatedExam] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setStatus({ type: "loading" });
    try {
      const { data } = await teacherAPI.createExam({
        title, subject,
        questions: questions.map((q) => ({ ...q, total_marks: Number(q.total_marks) })),
      });
      setStatus({ type: "success", message: "Exam created — see IDs below." });
      setCreatedExam(data);
      setTitle(""); setSubject("");
      setQuestions([{ question_text: "", total_marks: 10, rubric: "" }]);
      onCreated?.();
    } catch (err) {
      setStatus({ type: "error", message: "Could not create exam. Check all fields are filled in." });
    }
  };

  return (
    <div className="card">
      <h3>Create exam</h3>
      <form onSubmit={handleSubmit}>
        <div className="field">
          <label htmlFor="title">Title</label>
          <input id="title" required value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Biology Midterm" />
        </div>
        <div className="field">
          <label htmlFor="exam-subject">Subject</label>
          <input id="exam-subject" required value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="e.g. Biology" />
        </div>

        <label>Questions</label>
        {questions.map((q, i) => (
          <div key={i} className="card" style={{ marginBottom: "0.75rem", background: "#fbf8f1" }}>
            <div className="field">
              <label>Question text</label>
              <textarea rows={2} required value={q.question_text}
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
                <input required value={q.rubric} placeholder="e.g. 5 key points, 2 marks each, total 10"
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
          <p style={{ margin: 0 }}><strong>Exam ID: {createdExam.id}</strong></p>
          <p style={{ margin: "0.4em 0 0" }}>Question IDs:</p>
          <ul style={{ margin: "0.2em 0 0" }}>
            {createdExam.questions.map((q) => (
              <li key={q.id}>#{q.id} — {q.question_text.slice(0, 50)}{q.question_text.length > 50 ? "..." : ""}</li>
            ))}
          </ul>
          <p className="muted" style={{ fontSize: "0.8rem", marginBottom: 0 }}>
            Give students the Exam ID and the Question ID for whichever question they're answering.
          </p>
        </div>
      )}
    </div>
  );
}

function ExamsAndResults({ exams, onSelectExam, selectedExamId, results }) {
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
          <h3>Results for exam #{selectedExamId}</h3>
          {results.length === 0 && <p className="muted">No submissions graded yet.</p>}
          {results.length > 0 && (
            <table>
              <thead>
                <tr><th>Question</th><th>Marks</th><th>OCR conf.</th><th>Similarity</th><th>Status</th></tr>
              </thead>
              <tbody>
                {results.map((r) => (
                  <tr key={r.id}>
                    <td>Q{r.question}</td>
                    <td>{r.marks_awarded ?? "—"} / {r.total_marks}</td>
                    <td>{r.ocr_confidence != null ? `${r.ocr_confidence.toFixed(1)}%` : "—"}</td>
                    <td>{r.similarity_score != null ? r.similarity_score.toFixed(2) : "—"}</td>
                    <td>
                      <span className={`badge ${r.flagged ? "badge-flagged" : "badge-graded"}`}>
                        {r.flagged ? r.flag_reason?.replaceAll("_", " ") : "graded"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
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
  const [results, setResults] = useState([]);
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
      const { data } = await teacherAPI.examResults(examId);
      setResults(data);
    } catch {
      setResults([]);
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
        results={results}
      />
      <ReviewQueueCard queue={queue} />
    </div>
  );
}