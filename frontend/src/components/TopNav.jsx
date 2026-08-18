import { useNavigate } from "react-router-dom";
import { authAPI, tokenStore } from "../services/api";

export default function TopNav({ title }) {
  const navigate = useNavigate();
  const user = tokenStore.getUser();

  const handleLogout = async () => {
    try {
      await authAPI.logout(tokenStore.getRefresh());
    } catch {
      // best-effort; clear local state regardless
    }
    tokenStore.clear();
    navigate("/login");
  };

  return (
    <header style={{
      borderBottom: "1px solid var(--paper-line)",
      background: "#fffdf8",
    }}>
      <div className="container" style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "1rem 1.5rem",
      }}>
        <div>
          <h2 style={{ margin: 0 }}>{title}</h2>
          {user && <p className="muted" style={{ margin: 0, fontSize: "0.8rem" }}>{user.name} · {user.role}</p>}
        </div>
        <button className="btn btn-outline" onClick={handleLogout}>Sign out</button>
      </div>
    </header>
  );
}
