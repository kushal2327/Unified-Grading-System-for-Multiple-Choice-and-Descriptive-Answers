import axios from "axios";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000/api";

// ---- Token storage helpers ----
// Tokens are stored per-role (student_*, teacher_*, admin_*) so that
// switching between accounts in the same browser never overwrites the
// other role's session. The generic keys always mirror the most recent
// login (the "active" session) and are kept for backwards compatibility.
const ALL_ROLES = ["student", "teacher", "admin"];

export const tokenStore = {
  getAccess: (role) =>
    (role ? localStorage.getItem(`${role}_access_token`) : null) ||
    localStorage.getItem("access_token"),
  getRefresh: (role) =>
    (role ? localStorage.getItem(`${role}_refresh_token`) : null) ||
    localStorage.getItem("refresh_token"),
  set: (access, refresh, role) => {
    const prefix = role ? `${role}_` : "";
    localStorage.setItem(`${prefix}access_token`, access);
    if (refresh) localStorage.setItem(`${prefix}refresh_token`, refresh);
    // keep the active-session keys in sync so routing/logout still work
    localStorage.setItem("access_token", access);
    if (refresh) localStorage.setItem("refresh_token", refresh);
  },
  clear: (role) => {
    const roles = role ? [role] : ALL_ROLES;
    roles.forEach((r) => {
      localStorage.removeItem(`${r}_access_token`);
      localStorage.removeItem(`${r}_refresh_token`);
      localStorage.removeItem(`${r}_user`);
    });
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    localStorage.removeItem("user");
  },
  getUser: (role) => {
    const raw =
      (role ? localStorage.getItem(`${role}_user`) : null) ||
      localStorage.getItem("user");
    return raw ? JSON.parse(raw) : null;
  },
  setUser: (user, role) => {
    localStorage.setItem("user", JSON.stringify(user));
    if (role) localStorage.setItem(`${role}_user`, JSON.stringify(user));
  },
};

function createApi(role) {
  const client = axios.create({ baseURL: API_BASE_URL });

  // Attach the role's access token to every request.
  client.interceptors.request.use((config) => {
    const token = tokenStore.getAccess(role);
    if (token) config.headers.Authorization = `Bearer ${token}`;
    return config;
  });

  // On a 401, try refreshing the access token once, then retry the request.
  let refreshPromise = null;

  client.interceptors.response.use(
    (response) => response,
    async (error) => {
      const original = error.config;
      if (error.response?.status === 401 && !original._retry) {
        original._retry = true;
        const refresh = tokenStore.getRefresh(role);
        if (!refresh) {
          tokenStore.clear(role);
          return Promise.reject(error);
        }
        try {
          if (!refreshPromise) {
            refreshPromise = axios
              .post(`${API_BASE_URL}/auth/login/refresh`, { refresh })
              .finally(() => { refreshPromise = null; });
          }
          const { data } = await refreshPromise;
          tokenStore.set(data.access, data.refresh || refresh, role);
          original.headers.Authorization = `Bearer ${data.access}`;
          return client(original);
        } catch (refreshError) {
          tokenStore.clear(role);
          window.location.href = "/login";
          return Promise.reject(refreshError);
        }
      }
      return Promise.reject(error);
    }
  );

  return client;
}

// Role-scoped API clients. authAPI uses the active session (generic keys);
// the student/teacher/admin clients always use their own role's token.
const api = createApi(null);
const studentApi = createApi("student");
const teacherApi = createApi("teacher");
const adminApi = createApi("admin");

// ---- Auth ----
export const authAPI = {
  register: (payload) => api.post("/auth/register", payload),
  login: (payload) => api.post("/auth/login", payload),
  logout: (refresh) => api.post("/auth/logout", { refresh }),
  me: () => api.get("/auth/me"),
};

// ---- Teacher ----
export const teacherAPI = {
  uploadMaterial: (formData) =>
    teacherApi.post("/teacher/upload-material", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    }),
  listMaterials: () => teacherApi.get("/teacher/materials"),
  createExam: (payload) => teacherApi.post("/teacher/create-exam", payload),
  listExams: () => teacherApi.get("/teacher/exams"),
  updateExam: (examId, payload) => teacherApi.patch(`/teacher/exams/${examId}`, payload),
  deleteExam: (examId) => teacherApi.delete(`/teacher/exams/${examId}`),
  examResults: (examId) => teacherApi.get(`/teacher/results/${examId}`),
  examSubmissions: (examId) => teacherApi.get(`/teacher/submissions/${examId}`),
  reviewQueue: () => teacherApi.get("/teacher/review-queue"),
  reviewOverride: (resultId, payload) => teacherApi.post(`/teacher/review/${resultId}`, payload),
  materialChunks: (materialId) => teacherApi.get(`/teacher/materials/${materialId}/chunks`),
  visionStatus: () => teacherApi.get("/teacher/vision-status"),
};

// ---- Student ----
export const studentAPI = {
  submitAnswer: (formData) =>
    studentApi.post("/student/submit-answer", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    }),
  examResults: (examId) => studentApi.get(`/student/results/${examId}`),
  deleteResult: (resultId) => studentApi.delete(`/student/result/${resultId}`),
  examQuestions: (examId) => studentApi.get(`/student/exams/${examId}`),
  examLookupByCode: (code) => studentApi.get("/student/exams/lookup", { params: { code } }),
};

// ---- Admin ----
export const adminAPI = {
  reviewQueue: (statusFilter) =>
    adminApi.get("/admin/review-queue", { params: statusFilter ? { status: statusFilter } : {} }),
  overrideResult: (resultId, payload) => adminApi.post(`/admin/review/${resultId}`, payload),
  analytics: () => adminApi.get("/admin/analytics"),
};

export default api;