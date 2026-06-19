const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export class ApiError extends Error {
  constructor(status, detail) {
    super(typeof detail === "string" ? detail : JSON.stringify(detail));
    this.status = status;
    this.detail = detail;
  }
}

export function getApiKey() {
  return localStorage.getItem("apiKey") || "";
}

export function setApiKey(key) {
  localStorage.setItem("apiKey", key);
}

async function apiFetch(path, options = {}) {
  const headers = {
    "X-API-Key": getApiKey(),
    ...options.headers,
  };
  if (options.body) {
    headers["Content-Type"] = "application/json";
  }

  const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail ?? detail;
    } catch {
      // response had no JSON body
    }
    if (response.status === 401 && window.location.pathname !== "/settings") {
      sessionStorage.setItem("authMessage", "Your API key is missing or invalid. Please set a valid key.");
      window.location.assign("/settings");
    }
    throw new ApiError(response.status, detail);
  }

  if (response.status === 204) {
    return null;
  }
  return response.json();
}

export function listSkills() {
  return apiFetch("/api/skills");
}

export function createSkill(data) {
  return apiFetch("/api/skills", { method: "POST", body: JSON.stringify(data) });
}

export function listApplications() {
  return apiFetch("/api/applications");
}

export function getApplication(id) {
  return apiFetch(`/api/applications/${id}`);
}

export function createApplication(data) {
  return apiFetch("/api/applications", { method: "POST", body: JSON.stringify(data) });
}

export function getPendingApproval(id) {
  return apiFetch(`/api/applications/${id}/pending-approval`);
}

export function approveApplication(id, approvedSkills) {
  return apiFetch(`/api/applications/${id}/approve`, {
    method: "POST",
    body: JSON.stringify({ approved_skills: approvedSkills }),
  });
}
