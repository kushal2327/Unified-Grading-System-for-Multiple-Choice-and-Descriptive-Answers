import TopNav from "../components/TopNav";
import ManualReviewDashboard from "../components/ManualReviewDashboard";

export default function AdminHome() {
  return (
    <div>
      <TopNav title="Admin review dashboard" />
      <div className="container">
        <ManualReviewDashboard />
      </div>
    </div>
  );
}
