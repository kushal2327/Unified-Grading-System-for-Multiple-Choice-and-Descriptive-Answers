import { useState } from "react";
import { teacherAPI } from "../services/api";

function toLocalDateValue(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

function toLocalTimeValue(iso) {
  if (!iso) return "23:59";
  const d = new Date(iso);
  const pad = (n) => String(n).padStart(2, "0");
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export default function EditExamCard({ exam, onSaved, onClose }) {
  const [title, setTitle] = useState(exam.title);
  const [subject, setSubject] = useState(exam.subject);
  const [accessCode, setAccessCode] = useState(exam.access_code);
  const [validUntil, setValidUntil] = useState(toLocalDateValue(exam.valid_until));
  const [deadlineTime, setDeadlineTime] = useState(toLocalTimeValue(exam.valid_until));
  const [questions, setQuestions] = useState(
    (exam.questions || []).map((q) => ({
      id: q.id,
      question_text: q.question_text,
      total_marks: q.total_marks,
      rubric: q.rubric,
    }))
  );
  const [status, setStatus] = useState(null);

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
    setStatus({ type: "loading", message: "Saving changes..." });
    try {
      const { data } = await teacherAPI.updateExam(exam.id, {
        title,
        subject,
        access_code: accessCode,
        valid_until: validUntil
          ? new Date(`${validUntil}T${deadlineTime}`).toISOString()
          : undefined,
        questions: questions.map((q) => ({
          ...(q.id ? { id: q.id } : {}),
          question_text: q.question_text,
          total_marks: Number(q.total_marks),
          rubric: q.rubric,
        })),
      });
      setStatus({ type: "success", message: "Exam updated." });
      onSaved?.(data);
    } catch (err) {
      const detail = err.response?.data;
      let message;
      if (detail?.detail) message = detail.detail;
      else if (detail && typeof detail === "object") {
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
        message = parts.join(" | ") || "Could not update exam.";
      } else {
        message = "Could not update exam. Check all fields are filled in.";
      }
      setStatus({ type: "error", message });
    }
  };

  return (
    <div className="card" style={{ border: "2px solid var(--ink-blue)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h3 style={{ margin: 0 }}>Edit exam #{exam.id}</h3>
        <button type="button" className="btn btn-outline" onClick={onClose}>Close</button>
      </div>
      <form onSubmit={handleSubmit}>
        <div style={{ display: "flex", gap: "0.75rem" }}>
          <div className="field" style={{ flex: 2 }}>
            <label htmlFor={`edit-title-${exam.id}`}>Title</label>
            <input id={`edit-title-${exam.id}`} required value={title} onChange={(e) => setTitle(e.target.value)} />
          </div>
          <div className="field" style={{ flex: 1 }}>
            <label htmlFor={`edit-subject-${exam.id}`}>Subject</label>
            <input id={`edit-subject-${exam.id}`} required value={subject} onChange={(e) => setSubject(e.target.value)} />
          </div>
        </div>

        <div style={{ display: "flex", gap: "0.75rem" }}>
          <div className="field" style={{ flex: 1 }}>
            <label htmlFor={`edit-code-${exam.id}`}>Exam code (4 digits)</label>
            <input
              id={`edit-code-${exam.id}`} required maxLength={4} inputMode="numeric" pattern="\d{4}"
              value={accessCode}
              onChange={(e) => setAccessCode(e.target.value.replace(/\D/g, "").slice(0, 4))}
            />
          </div>
          <div className="field" style={{ flex: 1 }}>
            <label htmlFor={`edit-until-${exam.id}`}>Due date</label>
            <input id={`edit-until-${exam.id}`} type="date" required value={validUntil}
              onChange={(e) => setValidUntil(e.target.value)} />
          </div>
          <div className="field" style={{ flex: 1 }}>
            <label htmlFor={`edit-time-${exam.id}`}>Due time</label>
            <input id={`edit-time-${exam.id}`} type="time" required value={deadlineTime}
              onChange={(e) => setDeadlineTime(e.target.value)} />
          </div>
        </div>

        <label>Questions</label>
        {questions.map((q, i) => (
          <div key={q.id ?? `new-${i}`} className="card" style={{ marginBottom: "0.75rem", background: "#fbf8f1" }}>
            {q.id != null && <p className="muted" style={{ margin: "0 0 0.4rem", fontSize: "0.75rem" }}>Question ID: #{q.id}</p>}
            <div className="field">
              <label>Question text</label>
              <textarea rows={6} required value={q.question_text}
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
                <input required value={q.rubric}
                  onChange={(e) => updateQuestion(i, "rubric", e.target.value)} />
              </div>
            </div>
            {q.id == null && questions.length > 1 && (
              <button type="button" className="btn btn-outline" onClick={() => removeQuestion(i)}>
                Remove question
              </button>
            )}
          </div>
        ))}
        <button type="button" className="btn btn-outline" onClick={addQuestion} style={{ marginBottom: "1rem" }}>
          + Add another question
        </button>

        <div style={{ display: "flex", gap: "0.75rem", alignItems: "center" }}>
          <button className="btn btn-primary" type="submit" disabled={status?.type === "loading"}>
            {status?.type === "loading" ? "Saving..." : "Save changes"}
          </button>
          {status?.message && (
            <span className={status.type === "error" ? "error-text" : "muted"}>{status.message}</span>
          )}
        </div>
      </form>
    </div>
  );
}