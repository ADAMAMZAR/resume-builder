import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { createApplication, ApiError } from "../api.js";
import ErrorBanner from "../components/ErrorBanner.jsx";

export default function NewApplication() {
  const navigate = useNavigate();
  const [form, setForm] = useState({ company_name: "", role_title: "", jd_text: "" });
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      const created = await createApplication(form);
      navigate(`/applications/${created.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Failed to create application");
      setSubmitting(false);
    }
  }

  return (
    <div className="max-w-2xl">
      <h1 className="mb-2 text-3xl font-bold">Resume Architect</h1>
      <p className="mb-6 text-gray-600">
        Paste your target job description to begin the AI alignment.
      </p>
      <ErrorBanner message={error} />
      <form onSubmit={handleSubmit} className="space-y-4 rounded-xl border border-gray-200 bg-white p-6">
        <div>
          <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-gray-500">
            Company Name
          </label>
          <input
            required
            value={form.company_name}
            onChange={(e) => setForm({ ...form, company_name: e.target.value })}
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-gray-500">
            Role Title
          </label>
          <input
            required
            value={form.role_title}
            onChange={(e) => setForm({ ...form, role_title: e.target.value })}
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-gray-500">
            Job Description
          </label>
          <textarea
            required
            rows={8}
            value={form.jd_text}
            onChange={(e) => setForm({ ...form, jd_text: e.target.value })}
            placeholder="Paste the target job description here..."
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
          />
        </div>
        <button
          type="submit"
          disabled={submitting}
          className="w-full rounded-lg bg-black px-4 py-3 text-sm font-medium text-white disabled:opacity-50"
        >
          {submitting ? "Analyzing..." : "Run AI Analysis"}
        </button>
      </form>
    </div>
  );
}
