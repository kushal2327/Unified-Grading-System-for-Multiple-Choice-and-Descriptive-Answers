import TopNav from "../components/TopNav";
import TeacherDashboard from "../components/TeacherDashboard";

export default function TeacherHome() {
  return (
    <div>
      <TopNav title="Teacher dashboard" />
      <div className="container">
        <TeacherDashboard />
      </div>
    </div>
  );
}
