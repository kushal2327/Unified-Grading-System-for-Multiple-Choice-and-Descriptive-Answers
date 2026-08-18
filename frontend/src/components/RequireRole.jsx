import { Navigate } from "react-router-dom";
import { tokenStore } from "../services/api";

export default function RequireRole({ role, children }) {
  const token = tokenStore.getAccess();
  const user = tokenStore.getUser();

  if (!token || !user) return <Navigate to="/login" replace />;
  if (user.role !== role) return <Navigate to="/login" replace />;

  return children;
}
