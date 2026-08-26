# Frontend — React + Vite

Single-page application for the grading system, served as static files in production.

## Development

```bash
npm install
npm run dev       # Vite dev server on http://localhost:3000
npm run build     # Output to dist/
npm run lint      # Oxlint
npm run preview   # Preview production build
```

## Tech

- React 19, React Router v7, Axios
- Vite 5 with `@vitejs/plugin-react`
- Oxlint for linting

## Role-Based Routes

| Route | Role | Description |
|-------|------|-------------|
| `/login` | All | Login page |
| `/register` | All | Registration page |
| `/teacher` | Teacher | Exam creation, material upload, analytics |
| `/student` | Student | Exam list, answer submission, results |
| `/admin` | Admin | Manual review queue, system oversight |
