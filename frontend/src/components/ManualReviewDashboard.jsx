import { useEffect, useState } from "react";
import { adminAPI } from "../services/api";
import AnalyticsPanel from "./AnalyticsPanel";

function OverrideForm({ item, onDone }) {
  const [marks, setMarks] = useState("");
  const [feedback, setFeedback] = useState("");
  const [status, setStatus] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setStatus({ type: "loading" });
    try {
      await adminAPI.overrideResult(item.result.id, {
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
    <form onSubmit={handleSubmit} style={{ marginTop: "0.8rem" }}>
      <div style={{ display: "flex", gap: "0.75rem" }}>
        <div className="field" style={{ flex: 1 }}>
          <label>Marks (0–{item.result.total_marks})</label>
          <input type="number" step="0.5" min={0} max={item.result.total_marks} required
            value={marks} onChange={(e) => setMarks(e.target.value)} />
        </div>
      </div>
      <div className="field">
        <label>Feedback</label>
        <textarea rows={3} required value={feedback} onChange={(e) => setFeedback(e.target.value)} />
      </div>
      <button className="btn btn-primary" type="submit" disabled={status?.type === "loading"}>
        {status?.type === "loading" ? "Saving..." : "Save override"}
      </button>
      {status?.message && <p className="error-text">{status.message}</p>}
    </form>
  );
}

function FlaggedItem({ item, onReviewed }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="card" style={{ marginBottom: "0.9rem", background: "#fbf8f1" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <span className="badge badge-flagged">{item.reason.replaceAll("_", " ")}</span>
        <span className="muted" style={{ fontSize: "0.8rem" }}>Result #{item.result.id}</span>
      </div>

      <p style={{ margin: "0.6rem 0 0.3rem" }}><strong>OCR (cleaned):</strong></p>
      <p className="muted" style={{ margin: 0 }}>{item.result.ocr_cleaned_text || "(none extracted)"}</p>

      {item.result.retrieved_chunks?.length > 0 && (
        <>
          <p style={{ margin: "0.6rem 0 0.3rem" }}><strong>Retrieved reference chunks:</strong></p>
          {item.result.retrieved_chunks.map((chunk, i) => (
            <p key={i} className="muted" style={{ margin: "0 0 0.4rem", fontSize: "0.85rem" }}>{chunk}</p>
          ))}
        </>
      )}

      {item.result.feedback && (
        <>
          <p style={{ margin: "0.6rem 0 0.3rem" }}><strong>LLM feedback (if any):</strong></p>
          <p className="muted" style={{ margin: 0 }}>{item.result.feedback}</p>
        </>
      )}

      <p className="muted" style={{ marginTop: "0.6rem", fontSize: "0.8rem" }}>
        OCR confidence: {item.result.ocr_confidence?.toFixed(1) ?? "—"}%
        {" · "}Similarity: {item.result.similarity_score?.toFixed(2) ?? "n/a"}
        {" · "}Marks so far: {item.result.marks_awarded ?? "—"} / {item.result.total_marks}
      </p>

      {!expanded ? (
        <button className="btn btn-outline" onClick={() => setExpanded(true)}>Override marks & feedback</button>
      ) : (
        <>
          <OverrideForm item={item} onDone={onReviewed} />
          <button className="btn btn-outline" style={{ marginTop: "0.6rem" }} onClick={() => setExpanded(false)}>
            Close
          </button>
        </>
      )}
    </div>
  );
}

export default function ManualReviewDashboard() {
  const [queue, setQueue] = useState([]);
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);

  const loadAll = async () => {
    setLoading(true);
    try {
      const [queueRes, analyticsRes] = await Promise.all([
        adminAPI.reviewQueue("pending"),
        adminAPI.analytics(),
      ]);
      setQueue(queueRes.data);
      setAnalytics(analyticsRes.data);
    } catch {
      setQueue([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadAll(); }, []);

  return (
    <div style={{ display: "grid", gap: "1.5rem" }}>
      <AnalyticsPanel analytics={analytics} />
      <div className="card">
        <h3>Flagged answers — all exams</h3>
        {loading && <p className="muted">Loading...</p>}
        {!loading && queue.length === 0 && <p className="muted">Nothing pending review.</p>}
        {queue.map((item) => (
          <FlaggedItem key={item.id} item={item} onReviewed={loadAll} />
        ))}
      </div>
    </div>
  );
}
