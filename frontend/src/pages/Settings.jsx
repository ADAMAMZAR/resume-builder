import { useEffect, useState } from "react";
import { getApiKey, setApiKey } from "../api.js";

export default function Settings() {
  const [key, setKey] = useState(getApiKey());
  const [saved, setSaved] = useState(false);
  const [authMessage, setAuthMessage] = useState("");

  useEffect(() => {
    const message = sessionStorage.getItem("authMessage");
    if (message) {
      setAuthMessage(message);
      sessionStorage.removeItem("authMessage");
    }
  }, []);

  function handleSave(e) {
    e.preventDefault();
    setApiKey(key.trim());
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  return (
    <div className="max-w-md">
      <h1 className="mb-2 text-3xl font-bold">Settings</h1>
      {authMessage && (
        <div className="mb-4 rounded-lg border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-800">
          {authMessage}
        </div>
      )}
      <p className="mb-6 text-gray-600">
        Paste the API key issued to you. It's stored only in this browser and sent as the
        <code className="mx-1 rounded bg-gray-200 px-1">X-API-Key</code> header on every request.
      </p>
      <form onSubmit={handleSave} className="rounded-xl border border-gray-200 bg-white p-6">
        <label htmlFor="apiKey" className="mb-2 block text-xs font-semibold uppercase tracking-wide text-gray-500">
          API Key
        </label>
        <input
          id="apiKey"
          type="text"
          value={key}
          onChange={(e) => setKey(e.target.value)}
          className="mb-4 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
          placeholder="paste your API key"
        />
        <button type="submit" className="rounded-lg bg-black px-4 py-2 text-sm font-medium text-white">
          Save
        </button>
        {saved && <span className="ml-3 text-sm text-green-600">Saved</span>}
      </form>
    </div>
  );
}
