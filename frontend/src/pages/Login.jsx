import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { authAPI, tokenStore } from "../services/api";

export default function Login() {
  const navigate = useNavigate();
  const [form, setForm] = useState({ email: "", password: "" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleChange = (e) => setForm({ ...form, [e.target.name]: e.target.value });

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const { data } = await authAPI.login(form);
      tokenStore.set(data.access, data.refresh);
      tokenStore.setUser(data.user);

      if (data.user.role === "teacher") navigate("/teacher");
      else if (data.user.role === "student") navigate("/student");
      else if (data.user.role === "admin") navigate("/admin");
      else navigate("/");
    } catch (err) {
      setError(
        err.response?.data?.detail ||
        "Login failed. Check your email and password."
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="container" style={{ maxWidth: 420, paddingTop: "4rem" }}>
      <div className="card">
        <h1 style={{ marginBottom: "0.15em" }}>Sign in</h1>
        <p className="muted" style={{ marginTop: 0, marginBottom: "1.5rem" }}>
          Descriptive Answer Grading System
        </p>

        <form onSubmit={handleSubmit}>
          <div className="field">
            <label htmlFor="email">Email</label>
            <input
              id="email" name="email" type="email" required
              value={form.email} onChange={handleChange}
              placeholder="you@school.edu"
            />
          </div>
          <div className="field">
            <label htmlFor="password">Password</label>
            <input
              id="password" name="password" type="password" required
              value={form.password} onChange={handleChange}
              placeholder="••••••••"
            />
          </div>

          {error && <p className="error-text">{error}</p>}

          <button className="btn btn-primary" type="submit" disabled={loading} style={{ width: "100%", justifyContent: "center" }}>
            {loading ? "Signing in..." : "Sign in"}
          </button>
        </form>

        <p className="muted" style={{ marginTop: "1.2rem", fontSize: "0.85rem" }}>
          No account? <Link to="/register">Register here</Link>
        </p>
      </div>
    </div>
  );
}
