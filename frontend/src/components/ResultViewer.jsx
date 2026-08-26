export default function ResultViewer({ result }) {
  const justification = result.justification || {};
  const points = Object.entries(justification);

  const uploadedAt = result.created_at
    ? new Date(result.created_at).toLocaleString(undefined, {
        year: "numeric", month: "short", day: "numeric",
        hour: "numeric", minute: "2-digit",
      })
    : null;

  return (
    <div className="card" style={{ background: "#fbf8f1" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <h3 style={{ margin: 0 }}>
          Marks: {result.marks_awarded ?? "—"} / {result.total_marks}
        </h3>
        {result.flagged && (
          <span className="badge badge-flagged">{result.flag_reason?.replaceAll("_", " ")}</span>
        )}
      </div>

      {uploadedAt && (
        <p className="muted" style={{ margin: "0.3rem 0 0", fontSize: "0.78rem" }}>
          Uploaded: {uploadedAt}
        </p>
      )}

      {result.flagged && !result.feedback && (
        <p className="muted" style={{ marginTop: "0.6rem" }}>
          This answer is pending manual review — a teacher/admin will grade it directly.
        </p>
      )}

      {result.feedback && (
        <div style={{ marginTop: "0.8rem" }}>
          <label style={{ marginBottom: "0.2em" }}>Feedback</label>
          <p style={{ margin: 0 }}>{result.feedback}</p>
        </div>
      )}

      {points.length > 0 && (
        <div style={{ marginTop: "0.8rem" }}>
          <label style={{ marginBottom: "0.3em" }}>Justification</label>
          <table>
            <thead>
              <tr><th>Point</th><th>Status</th><th>Marks</th><th>Comment</th></tr>
            </thead>
            <tbody>
              {points.map(([key, val]) => (
                <tr key={key}>
                  <td>{key}</td>
                  <td>
                    <span className={`badge ${
                      val.status === "full" ? "badge-graded" :
                      val.status === "partial" ? "badge-pending" : "badge-flagged"
                    }`}>
                      {val.status}
                    </span>
                  </td>
                  <td>{val.marks}</td>
                  <td>{val.comment}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {(result.ocr_confidence != null || result.similarity_score != null) && (
        <div style={{ marginTop: "0.8rem", fontSize: "0.8rem" }}>
          {result.ocr_confidence != null && (
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.3rem" }}>
              <span className="muted">OCR confidence:</span>
              <div style={{
                width: "80px", height: "6px", background: "#e0e0e0", borderRadius: "3px", overflow: "hidden"
              }}>
                <div style={{
                  width: `${result.ocr_confidence}%`, height: "100%",
                  background: result.ocr_confidence >= 70 ? "#4caf50" : result.ocr_confidence >= 40 ? "#ff9800" : "#f44336",
                  borderRadius: "3px",
                }} />
              </div>
              <span style={{
                fontWeight: 600,
                color: result.ocr_confidence >= 70 ? "#4caf50" : result.ocr_confidence >= 40 ? "#ff9800" : "#f44336",
              }}>{result.ocr_confidence.toFixed(1)}%</span>
            </div>
          )}

        </div>
      )}
    </div>
  );
}
