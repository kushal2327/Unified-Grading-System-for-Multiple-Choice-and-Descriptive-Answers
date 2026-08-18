import TopNav from "../components/TopNav";
import StudentDashboard from "../components/StudentDashboard";

export default function StudentHome() {
  return (
    <div>
      <TopNav title="Student dashboard" />
      <div className="container">
        <StudentDashboard />
      </div>
    </div>
  );
}
