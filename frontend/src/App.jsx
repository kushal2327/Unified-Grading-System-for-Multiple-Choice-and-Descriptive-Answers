import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Login from "./pages/Login";
import Register from "./pages/Register";
import TeacherHome from "./pages/TeacherHome";
import StudentHome from "./pages/StudentHome";
import AdminHome from "./pages/AdminHome";
import RequireRole from "./components/RequireRole";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/login" replace />} />
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />

        <Route
          path="/teacher"
          element={<RequireRole role="teacher"><TeacherHome /></RequireRole>}
        />
        <Route
          path="/student"
          element={<RequireRole role="student"><StudentHome /></RequireRole>}
        />
        <Route
          path="/admin"
          element={<RequireRole role="admin"><AdminHome /></RequireRole>}
        />

        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
