import { useEffect, useState } from "react";
import { teacherAPI } from "../services/api";

function MaterialRow({ material }) {
  const [expanded, setExpanded] = useState(false);
  const [chunks, setChunks] = useState(null);
  const [loading, setLoading] = useState(false);

  const toggle = async () => {
    if (!expanded && chunks === null) {
      setLoading(true);
      try {
        const { data } = await teacherAPI.materialChunks(material.id);
        setChunks(data.chunks);
      } catch {
        setChunks([]);
      } finally {
        setLoading(false);
      }
    }
    setExpanded(!expanded);
  };

  return (
    <>
      <tr>
        <td>{material.filename}</td>
        <td>{material.subject}</td>
        <td>
          <span className={`badge ${material.chunked ? "badge-graded" : "badge-pending"}`}>
            {material.chunked ? "processed" : "processing"}
          </span>
        </td>
        <td>
          <button className="btn btn-outline" onClick={toggle}>
            {expanded ? "Hide chunks" : "View extracted chunks"}
          </button>
        </td>
      </tr>
      {expanded && (
        <tr>
          <td colSpan={4}>
            {loading && <p className="muted">Loading chunks...</p>}
            {!loading && chunks && chunks.length === 0 && (
              <p className="muted">No chunks found — this material may not have finished processing.</p>
            )}
            {!loading && chunks && chunks.map((c) => (
              <div key={c.chunk_index} className="card" style={{ marginBottom: "0.5rem", background: "#fbf8f1" }}>
                <p className="muted" style={{ margin: "0 0 0.3em", fontSize: "0.75rem" }}>
                  Chunk {c.chunk_index}
                </p>
                <p style={{ margin: 0, fontSize: "0.88rem" }}>{c.text}</p>
              </div>
            ))}
          </td>
        </tr>
      )}
    </>
  );
}

export default function MaterialsList() {
  const [materials, setMaterials] = useState([]);

  useEffect(() => {
    teacherAPI.listMaterials()
      .then(({ data }) => setMaterials(data))
      .catch(() => setMaterials([]));
  }, []);

  return (
    <div className="card">
      <h3>Your uploaded materials</h3>
      {materials.length === 0 && <p className="muted">No materials uploaded yet.</p>}
      {materials.length > 0 && (
        <table>
          <thead>
            <tr><th>File</th><th>Subject</th><th>Status</th><th></th></tr>
          </thead>
          <tbody>
            {materials.map((m) => <MaterialRow key={m.id} material={m} />)}
          </tbody>
        </table>
      )}
    </div>
  );
}