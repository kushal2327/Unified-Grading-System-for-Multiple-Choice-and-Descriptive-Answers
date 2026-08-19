import axios from "axios";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000/api";

const api = axios.create({ baseURL: API_BASE_URL });

// ---- Token storage helpers ----
export const tokenStore = {
  getAccess: () => localStorage.getItem("access_token"),
  getRefresh: () => localStorage.getItem("refresh_token"),
  set: (access, refresh) => {
    localStorage.setItem("access_token", access);
    if (refresh) localStorage.setItem("refresh_token", refresh);
  },
  clear: () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    localStorage.removeItem("user");
  },
  getUser: () => {
    const raw = localStorage.getItem("user");
    return raw ? JSON.parse(raw) : null;
  },
  setUser: (user) => localStorage.setItem("user", JSON.stringify(user)),
};

// Attach access token to every request
api.interceptors.request.use((config) => {
  const token = tokenStore.getAccess();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// On a 401, try refreshing the access token once, then retry the request.
let refreshPromise = null;

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;
    if (error.response?.status === 401 && !original._retry) {
      original._retry = true;
      const refresh = tokenStore.getRefresh();
      if (!refresh) {
        tokenStore.clear();
        return Promise.reject(error);
      }
      try {
        if (!refreshPromise) {
          refreshPromise = axios
            .post(`${API_BASE_URL}/auth/login/refresh`, { refresh })
            .finally(() => { refreshPromise = null; });
        }
        const { data } = await refreshPromise;
        tokenStore.set(data.access, refresh);
        original.headers.Authorization = `Bearer ${data.access}`;
        return api(original);
      } catch (refreshError) {
        tokenStore.clear();
        window.location.href = "/login";
        return Promise.reject(refreshError);
      }
    }
    return Promise.reject(error);
  }
);

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
    api.post("/teacher/upload-material", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    }),
  listMaterials: () => api.get("/teacher/materials"),
  createExam: (payload) => api.post("/teacher/create-exam", payload),
  listExams: () => api.get("/teacher/exams"),
  examResults: (examId) => api.get(`/teacher/results/${examId}`),
  examSubmissions: (examId) => api.get(`/teacher/submissions/${examId}`),
  reviewQueue: () => api.get("/teacher/review-queue"),
  materialChunks: (materialId) => api.get(`/teacher/materials/${materialId}/chunks`),
};

// ---- Student ----
export const studentAPI = {
  submitAnswer: (formData) =>
    api.post("/student/submit-answer", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    }),
  examResults: (examId) => api.get(`/student/results/${examId}`),
  examQuestions: (examId) => api.get(`/student/exams/${examId}`),
  examLookupByCode: (code) => api.get("/student/exams/lookup", { params: { code } }),
};

// ---- Admin ----
export const adminAPI = {
  reviewQueue: (statusFilter) =>
    api.get("/admin/review-queue", { params: statusFilter ? { status: statusFilter } : {} }),
  overrideResult: (resultId, payload) => api.post(`/admin/review/${resultId}`, payload),
  analytics: () => api.get("/admin/analytics"),
};

export default api;
