import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import {
  getApplication,
  getPendingApproval,
  approveApplication,
  ApiError,
} from "../api.js";
import ErrorBanner from "../components/ErrorBanner.jsx";

const POLL_INTERVAL_MS = 2000;
const TERMINAL_STATUSES = ["awaiting_human", "completed", "extraction_failed", "generation_failed"];

export default function ApplicationDetail() {
  const { id } = useParams();
  const [application, setApplication] = useState(null);
  const [pendingSkills, setPendingSkills] = useState(null);
  const [checked, setChecked] = useState({});
  const [error, setError] = useState("");
  const [notFound, setNotFound] = useState(false);
  const [approving, setApproving] = useState(false);
  const pollRef = useRef(null);

  const fetchApplication = useCallback(async () => {
    try {
      const app = await getApplication(id);
      setApplication(app);
      setNotFound(false);
      return app;
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setNotFound(true);
      } else {
        setError(err instanceof ApiError ? err.detail : "Failed to load application");
      }
      return null;
    }
  }, [id]);

  useEffect(() => {
    let cancelled = false;

    async function tick() {
      const app = await fetchApplication();
      if (cancelled || !app) return;
      if (!TERMINAL_STATUSES.includes(app.status)) {
        pollRef.current = setTimeout(tick, POLL_INTERVAL_MS);
      }
    }

    tick();
    return () => {
      cancelled = true;
      if (pollRef.current) clearTimeout(pollRef.current);
    };
  }, [fetchApplication]);

  useEffect(() => {
    if (application?.status !== "awaiting_human") {
      setPendingSkills(null);
      return;
    }
    getPendingApproval(id)
      .then((data) => {
        setPendingSkills(data.extracted_skills);
        const initial = {};
        for (const category of Object.values(data.extracted_skills)) {
          for (const skill of category) initial[skill] = true;
        }
        setChecked(initial);
      })
      .catch((err) => setError(err instanceof ApiError ? err.detail : "Failed to load pending skills"));
  }, [application?.status, id]);

  async function handleApprove() {
    setApproving(true);
    setError("");
    const approvedSkills = Object.entries(checked)
      .filter(([, isChecked]) => isChecked)
      .map(([name]) => name);
    try {
      const updated = await approveApplication(id, approvedSkills);
      setApplication(updated);
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        await fetchApplication();
      } else {
        setError(err instanceof ApiError ? err.detail : "Failed to approve application");
      }
    } finally {
      setApproving(false);
    }
  }

  if (notFound) {
    return <p className="text-gray-500">Application not found.</p>;
  }

  if (!application) {
    return <p className="text-gray-500">Loading...</p>;
  }

  return (
    <div className="max-w-3xl">
      <h1 className="mb-1 text-3xl font-bold">{application.role_title}</h1>
      <p className="mb-6 text-gray-600">{application.company_name}</p>
      <ErrorBanner message={error} />

      {(application.status === "pending_extraction" || application.status === "generating") && (
        <div className="rounded-xl border border-gray-200 bg-white p-6 text-gray-600">
          {application.status === "pending_extraction" ? "Extracting required skills..." : "Generating your tailored resume..."}
        </div>
      )}

      {(application.status === "extraction_failed" || application.status === "generation_failed") && (
        <div className="rounded-xl border border-red-300 bg-red-50 p-6 text-red-800">
          {application.status === "extraction_failed"
            ? "Skill extraction failed. Please create a new application."
            : "Resume generation failed. Please create a new application."}
        </div>
      )}

      {application.status === "awaiting_human" && pendingSkills && (
        <div className="rounded-xl border border-gray-200 bg-white p-6">
          <h2 className="mb-4 text-xs font-semibold uppercase tracking-wide text-gray-500">Key Skills</h2>
          {Object.entries(pendingSkills).map(([category, skillList]) => (
            <div key={category} className="mb-4">
              <h3 className="mb-2 text-sm font-medium capitalize">{category.replaceAll("_", " ")}</h3>
              <div className="flex flex-wrap gap-2">
                {skillList.map((skill) => (
                  <label
                    key={skill}
                    className="flex items-center gap-2 rounded-full border border-gray-300 px-3 py-1 text-sm"
                  >
                    <input
                      type="checkbox"
                      checked={!!checked[skill]}
                      onChange={(e) => setChecked({ ...checked, [skill]: e.target.checked })}
                    />
                    {skill}
                  </label>
                ))}
              </div>
            </div>
          ))}
          <button
            onClick={handleApprove}
            disabled={approving}
            className="mt-2 rounded-lg bg-black px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            {approving ? "Generating..." : "Approve & Generate"}
          </button>
        </div>
      )}

      {application.status === "completed" && application.final_resume_json && (
        <div className="space-y-6">
          <div className="rounded-xl border border-gray-200 bg-white p-6">
            <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">Summary</h2>
            <p className="mb-4 text-sm">{application.final_resume_json.summary}</p>
            <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">Skills</h2>
            <div className="mb-4 flex flex-wrap gap-2">
              {application.final_resume_json.skills_aligned.map((skill) => (
                <span key={skill} className="rounded-full bg-gray-200 px-2 py-0.5 text-xs">
                  {skill}
                </span>
              ))}
            </div>
            <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">Experience</h2>
            <div className="space-y-3">
              {application.final_resume_json.experience.map((exp, idx) => (
                <div key={idx}>
                  <p className="text-sm font-medium">
                    {exp.role} — {exp.company}
                  </p>
                  <ul className="ml-5 list-disc text-sm text-gray-600">
                    {exp.impact_bullets.map((bullet, bIdx) => (
                      <li key={bIdx}>{bullet}</li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </div>
          <div className="rounded-xl border border-gray-200 bg-white p-6">
            <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">Cover Letter</h2>
            <pre className="whitespace-pre-wrap text-sm">{application.final_cover_letter_md}</pre>
          </div>
        </div>
      )}
    </div>
  );
}
