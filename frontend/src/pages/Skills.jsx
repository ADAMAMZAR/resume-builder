import { useEffect, useState } from "react";
import { listSkills, createSkill, ApiError } from "../api.js";
import ErrorBanner from "../components/ErrorBanner.jsx";

const CATEGORY_LABELS = {
  hard_skill: "Hard Skill",
  soft_skill: "Soft Skill",
  tool: "Tool",
};

const emptyForm = { skill_name: "", category: "hard_skill", proficiency_level: "", context: "" };

export default function Skills() {
  const [skills, setSkills] = useState([]);
  const [form, setForm] = useState(emptyForm);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listSkills()
      .then(setSkills)
      .catch((err) => setError(err instanceof ApiError ? err.detail : "Failed to load skills"))
      .finally(() => setLoading(false));
  }, []);

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    try {
      const created = await createSkill({
        ...form,
        proficiency_level: form.proficiency_level || null,
        context: form.context || null,
      });
      setSkills((prev) => [created, ...prev]);
      setForm(emptyForm);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Failed to add skill");
    }
  }

  return (
    <div className="max-w-3xl">
      <h1 className="mb-6 text-3xl font-bold">My Skills</h1>
      <ErrorBanner message={error} />

      <form onSubmit={handleSubmit} className="mb-8 rounded-xl border border-gray-200 bg-white p-6">
        <h2 className="mb-4 text-xs font-semibold uppercase tracking-wide text-gray-500">Add Skill</h2>
        <div className="mb-3 grid grid-cols-2 gap-3">
          <input
            required
            placeholder="Skill name"
            value={form.skill_name}
            onChange={(e) => setForm({ ...form, skill_name: e.target.value })}
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
          />
          <select
            value={form.category}
            onChange={(e) => setForm({ ...form, category: e.target.value })}
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
          >
            {Object.entries(CATEGORY_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
          <input
            placeholder="Proficiency level (optional)"
            value={form.proficiency_level}
            onChange={(e) => setForm({ ...form, proficiency_level: e.target.value })}
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
          />
        </div>
        <textarea
          placeholder="Context (optional) — how you used this skill"
          value={form.context}
          onChange={(e) => setForm({ ...form, context: e.target.value })}
          className="mb-4 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
          rows={2}
        />
        <button type="submit" className="rounded-lg bg-black px-4 py-2 text-sm font-medium text-white">
          Add Skill
        </button>
      </form>

      {loading ? (
        <p className="text-gray-500">Loading...</p>
      ) : skills.length === 0 ? (
        <p className="text-gray-500">No skills yet. Add your first one above.</p>
      ) : (
        <ul className="space-y-2">
          {skills.map((skill) => (
            <li key={skill.id} className="rounded-xl border border-gray-200 bg-white p-4">
              <div className="flex items-center gap-2">
                <span className="font-medium">{skill.skill_name}</span>
                <span className="rounded-full bg-gray-200 px-2 py-0.5 text-xs">
                  {CATEGORY_LABELS[skill.category] || skill.category}
                </span>
                {skill.proficiency_level && (
                  <span className="text-xs text-gray-500">{skill.proficiency_level}</span>
                )}
              </div>
              {skill.context && <p className="mt-1 text-sm text-gray-600">{skill.context}</p>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
