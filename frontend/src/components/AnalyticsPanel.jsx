const PALETTE = {
  blue: "var(--ink-blue)",
  deep: "var(--ink-blue-deep)",
  green: "var(--accent-green)",
  amber: "var(--accent-amber)",
  red: "var(--accent-red)",
  soft: "var(--ink-soft)",
};

const STATUS_COLORS = { pending: PALETTE.amber, graded: PALETTE.green, flagged: PALETTE.red };

function Stat({ label, value, accent }) {
  return (
    <div
      style={{
        background: "#fffdf8",
        border: "1px solid var(--paper-line)",
        borderRadius: "var(--radius)",
        padding: "0.8rem 1rem",
        borderTop: `3px solid ${accent || "var(--ink-blue)"}`,
      }}
    >
      <div style={{ fontFamily: "var(--font-display)", fontSize: "1.45rem", color: "var(--ink-blue-deep)", lineHeight: 1.2 }}>
        {value ?? "—"}
      </div>
      <div className="muted" style={{ fontSize: "0.72rem", textTransform: "uppercase", letterSpacing: "0.04em" }}>
        {label}
      </div>
    </div>
  );
}

function VerticalBarChart({ data, height = 190, color = PALETTE.blue }) {
  const max = Math.max(1, ...data.map((d) => d.count));
  const width = 340;
  const padTop = 24;
  const padBottom = 30;
  const chartH = height - padTop - padBottom;
  const slot = width / data.length;
  const barW = Math.min(46, slot * 0.55);

  return (
    <svg viewBox={`0 0 ${width} ${height}`} style={{ width: "100%", height: "auto" }} role="img">
      <line x1="0" y1={height - padBottom} x2={width} y2={height - padBottom} stroke="var(--paper-line)" strokeWidth="1.5" />
      {data.map((d, i) => {
        const h = d.count === 0 ? 0 : Math.max(3, (d.count / max) * chartH);
        const x = i * slot + (slot - barW) / 2;
        const y = height - padBottom - h;
        return (
          <g key={d.label}>
            <rect x={x} y={y} width={barW} height={h} rx="2" fill={color} opacity={0.9} />
            <text
              x={x + barW / 2} y={y - 6} textAnchor="middle"
              fontSize="12" fontWeight="700" fill="var(--ink-blue-deep)"
            >
              {d.count}
            </text>
            <text
              x={x + barW / 2} y={height - padBottom + 16} textAnchor="middle"
              fontSize="10.5" fill="var(--ink-soft)"
            >
              {d.label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

function DonutChart({ percent, label, sublabel, color = PALETTE.red, size = 150 }) {
  const r = 56;
  const c = 2 * Math.PI * r;
  const clamped = Math.min(100, Math.max(0, percent ?? 0));

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "0.4rem" }}>
      <svg viewBox="0 0 140 140" width={size} height={size} role="img">
        <circle cx="70" cy="70" r={r} fill="none" stroke="var(--paper-line)" strokeWidth="14" />
        <circle
          cx="70" cy="70" r={r} fill="none"
          stroke={color} strokeWidth="14" strokeLinecap="round"
          strokeDasharray={`${(clamped / 100) * c} ${c}`}
          transform="rotate(-90 70 70)"
        />
        <text x="70" y="66" textAnchor="middle" fontSize="22" fontWeight="700" fill="var(--ink-blue-deep)">
          {clamped.toFixed(1)}%
        </text>
        <text x="70" y="84" textAnchor="middle" fontSize="10.5" fill="var(--ink-soft)">
          {label}
        </text>
      </svg>
      {sublabel && <span className="muted" style={{ fontSize: "0.78rem" }}>{sublabel}</span>}
    </div>
  );
}

function HBarList({ items, emptyText = "No data yet." }) {
  if (!items.length) return <p className="muted" style={{ fontSize: "0.85rem" }}>{emptyText}</p>;
  const max = Math.max(1, ...items.map((i) => i.value));
  return (
    <div style={{ display: "grid", gap: "0.55rem" }}>
      {items.map((item) => (
        <div key={item.label}>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.82rem", marginBottom: "0.15rem" }}>
            <span>{item.label}</span>
            <strong style={{ color: "var(--ink-blue-deep)" }}>{item.value}</strong>
          </div>
          <div style={{ background: "var(--accent-amber-soft)", borderRadius: 999, height: 9, overflow: "hidden" }}>
            <div
              style={{
                width: `${(item.value / max) * 100}%`,
                height: "100%",
                background: item.color || PALETTE.blue,
                borderRadius: 999,
                transition: "width 0.3s ease",
              }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

export default function AnalyticsPanel({ analytics }) {
  if (!analytics) return null;

  const statusItems = (analytics.submission_status_breakdown || []).map((row) => ({
    label: row.status.charAt(0).toUpperCase() + row.status.slice(1),
    value: row.count,
    color: STATUS_COLORS[row.status] || PALETTE.blue,
  }));

  const flagItems = (analytics.flag_reason_breakdown || []).map((row) => ({
    label: row.reason.replaceAll("_", " "),
    value: row.count,
    color: PALETTE.red,
  }));

  const ocrItems = (analytics.ocr_confidence_distribution || []).map((row) => ({
    label: row.label,
    value: row.count,
    color: PALETTE.amber,
  }));

  const hasScoreData = (analytics.score_distribution || []).some((b) => b.count > 0);

  return (
    <div className="card">
      <h3>Analytics</h3>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))", gap: "0.75rem" }}>
        <Stat label="Submissions" value={analytics.total_submissions} />
        <Stat label="Results graded" value={analytics.total_results} accent={PALETTE.green} />
        <Stat label="Flag rate" value={`${analytics.flag_rate_percent}%`} accent={PALETTE.red} />
        <Stat label="Avg score" value={analytics.average_score_percent != null ? `${analytics.average_score_percent}%` : null} accent={PALETTE.green} />
        <Stat label="Avg OCR conf." value={analytics.average_ocr_confidence != null ? `${analytics.average_ocr_confidence}%` : null} accent={PALETTE.amber} />
        <Stat label="Avg similarity" value={analytics.average_similarity != null ? analytics.average_similarity.toFixed(2) : null} accent={PALETTE.blue} />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1.4fr 1fr", gap: "1.5rem", marginTop: "1.5rem", alignItems: "center" }}>
        <div>
          <label>Score distribution</label>
          {hasScoreData ? (
            <VerticalBarChart data={analytics.score_distribution} />
          ) : (
            <p className="muted" style={{ fontSize: "0.85rem" }}>No graded answers yet.</p>
          )}
        </div>
        <div>
          <label>Flag rate</label>
          <DonutChart
            percent={analytics.flag_rate_percent}
            label={`${analytics.flagged_count}/${analytics.total_results} flagged`}
            sublabel="Share of answers sent to manual review"
          />
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1.5rem", marginTop: "1.5rem" }}>
        <div>
          <label>OCR confidence buckets</label>
          <HBarList items={ocrItems} emptyText="No OCR results yet." />
        </div>
        <div>
          <label>Submission status</label>
          <HBarList items={statusItems} emptyText="No submissions yet." />
          <div style={{ marginTop: "1.25rem" }}>
            <label>Flag reasons</label>
            <HBarList items={flagItems} emptyText="Nothing has been flagged." />
          </div>
        </div>
      </div>

      {(analytics.per_exam || []).length > 0 && (
        <div style={{ marginTop: "1.5rem" }}>
          <label>Performance by exam</label>
          <table>
            <thead>
              <tr><th>Exam</th><th>Subject</th><th>Submissions</th><th>Avg score</th><th>Flagged</th></tr>
            </thead>
            <tbody>
              {analytics.per_exam.map((e) => (
                <tr key={e.exam_id}>
                  <td><strong>{e.title}</strong></td>
                  <td className="muted">{e.subject}</td>
                  <td>{e.num_submissions}</td>
                  <td style={{ minWidth: 140 }}>
                    {e.avg_score_percent != null ? (
                      <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                        <div style={{ flex: 1, background: "var(--paper-line)", borderRadius: 999, height: 8, overflow: "hidden" }}>
                          <div
                            style={{
                              width: `${Math.min(100, e.avg_score_percent)}%`,
                              height: "100%",
                              background: e.avg_score_percent >= 60 ? PALETTE.green : e.avg_score_percent >= 40 ? PALETTE.amber : PALETTE.red,
                            }}
                          />
                        </div>
                        <span style={{ fontSize: "0.82rem", whiteSpace: "nowrap" }}>{e.avg_score_percent}%</span>
                      </div>
                    ) : (
                      <span className="muted">—</span>
                    )}
                  </td>
                  <td>{e.flagged_count > 0 ? <span className="badge badge-flagged">{e.flagged_count}</span> : <span className="muted">0</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
