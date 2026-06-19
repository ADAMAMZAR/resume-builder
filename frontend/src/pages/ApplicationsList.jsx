import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listApplications, ApiError } from "../api.js";
import ErrorBanner from "../components/ErrorBanner.jsx";

const STATUS_LABELS = {
  pending_extraction: "Extracting",
  extraction_failed: "Extraction Failed",
  awaiting_human: "Awaiting Review",
  generating: "Generating",
  generation_failed: "Generation Failed",
  completed: "Completed",
};

function statusBadgeClasses(status) {
  if (status === "completed") return "bg-green-100 text-green-800";
  if (status.endsWith("failed")) return "bg-red-100 text-red-800";
  return "bg-gray-200 text-gray-800";
}

export default function ApplicationsList() {
  const [applications, setApplications] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listApplications()
      .then(setApplications)
      .catch((err) => setError(err instanceof ApiError ? err.detail : "Failed to load applications"))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="max-w-3xl">
      <h1 className="mb-6 text-3xl font-bold">Applications</h1>
      <ErrorBanner message={error} />
      {loading ? (
        <p className="text-gray-500">Loading...</p>
      ) : applications.length === 0 ? (
        <p className="text-gray-500">
          No applications yet. <Link to="/applications/new" className="underline">Create one</Link>.
        </p>
      ) : (
        <ul className="space-y-2">
          {applications.map((app) => (
            <li key={app.id}>
              <Link
                to={`/applications/${app.id}`}
                className="flex items-center justify-between rounded-xl border border-gray-200 bg-white p-4 hover:border-gray-400"
              >
                <div>
                  <p className="font-medium">{app.role_title}</p>
                  <p className="text-sm text-gray-600">{app.company_name}</p>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-xs text-gray-500">
                    {new Date(app.created_at).toLocaleDateString()}
                  </span>
                  <span className={`rounded-full px-2 py-0.5 text-xs ${statusBadgeClasses(app.status)}`}>
                    {STATUS_LABELS[app.status] || app.status}
                  </span>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
