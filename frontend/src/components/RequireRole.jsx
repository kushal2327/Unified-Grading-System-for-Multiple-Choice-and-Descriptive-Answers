import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { tokenStore, authAPI } from "../services/api";

const HOME = { student: "/student", teacher: "/teacher", admin: "/admin" };

export default function RequireRole({ role, children }) {
  const [state, setState] = useState("loading");
  const [target, setTarget] = useState("/login");

  useEffect(() => {
    let active = true;
    (async () => {
      const token = tokenStore.getAccess();
      if (!token) {
        if (active) setState("login");
        return;
      }
      try {
        const { data } = await authAPI.me();
        if (!active) return;
        if (data.role !== role) {
          // Session is still valid — just send them to their own dashboard.
          // Clearing tokens here is what forced re-login when switching
          // between teacher/student accounts in the same browser.
          if (active) {
            setTarget(HOME[data.role] || "/login");
            setState("redirect");
          }
        } else {
          setState("ok");
        }
      } catch {
        // Tokens are genuinely dead (the axios interceptor already cleared
        // them after a failed refresh), so just show the login page.
        if (active) setState("login");
      }
    })();
    return () => { active = false; };
  }, [role]);

  if (state === "loading") return null;
  if (state === "redirect" || state === "login") return <Navigate to={target} replace />;
  return children;
}