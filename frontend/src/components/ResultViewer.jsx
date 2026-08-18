export default function ResultViewer({ result }) {
  const justification = result.justification || {};
  const points = Object.entries(justification);

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
        <p className="muted" style={{ marginTop: "0.8rem", fontSize: "0.8rem" }}>
          OCR confidence: {result.ocr_confidence?.toFixed(1) ?? "—"}%
          {" · "}
          Reference match: {result.similarity_score != null ? result.similarity_score.toFixed(2) : "n/a"}
        </p>
      )}
    </div>
  );
}
