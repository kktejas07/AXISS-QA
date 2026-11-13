import { useEffect, useState } from "react";
import { getAiSettings, saveAiSettings } from "../api/insights";
import type { AiSettings } from "../api/insights";
import { apiError } from "../utils/errors";
import { errorBox, field, hint, label } from "./ui";

const choices: { id: AiSettings["quality"]; name: string; about: string }[] = [
  { id: "fast", name: "Fast", about: "The quickest, least costly model for everything. Good for frequent scans." },
  { id: "balanced", name: "Balanced", about: "A stronger model for test scripts and summaries, a quick one for the rest. The default." },
  { id: "best", name: "Best", about: "The strongest model for everything. Slower and costs more." },
];

/** Which AI provider and model this organisation's scans and Wise use, and whose key pays for it. */
export function AiSettingsSection({ canEdit }: { canEdit: boolean }) {
  const [saved, setSaved] = useState<AiSettings | null>(null);
  const [quality, setQuality] = useState<AiSettings["quality"]>("balanced");
  const [provider, setProvider] = useState("anthropic");
  const [model, setModel] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [key, setKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const show = (data: AiSettings) => {
    setSaved(data);
    setQuality(data.quality);
    setProvider(data.provider);
    setModel(data.model ?? "");
    setBaseUrl(data.base_url ?? "");
    setKey("");
  };
  useEffect(() => {
    getAiSettings().then((r) => show(r.data)).catch(() => setError("The AI settings could not be loaded."));
  }, []);

  const save = async (body: Parameters<typeof saveAiSettings>[0], done: string) => {
    setError("");
    setNotice("");
    setBusy(true);
    try {
      show((await saveAiSettings(body)).data);
      setNotice(done);
    } catch (e) {
      setError(apiError(e, "The AI settings could not be saved."));
    } finally {
      setBusy(false);
    }
  };

  const chosen = saved?.providers.find((p) => p.id === provider);
  const own = provider !== "anthropic";
  const suggested = chosen ? (quality === "fast" ? chosen.fast : quality === "best" ? chosen.best : [chosen.fast, chosen.best].filter(Boolean).join(" and ")) : "";

  return (
    <section className="rounded-2xl border border-gray-300 bg-white p-6">
      <h2 className="text-lg font-bold">AI provider and model</h2>
      <p className="mb-4 max-w-[70ch] text-body">
        Choose who writes the test cases, scripts, summaries and Wise's answers, and speed against quality. Wiseflow uses Claude by default; with your own key you can use another provider and pay them directly.
      </p>
      {error && <p role="alert" className={`${errorBox} mb-4`}>{error}</p>}
      {notice && <p role="status" className="mb-4 rounded-[10px] border border-emerald-200 bg-emerald-50 px-4 py-3 text-emerald-900">{notice}</p>}
      {saved && (
        <form
          className="flex flex-col gap-5"
          onSubmit={(e) => {
            e.preventDefault();
            save({ quality, provider, model: model.trim() || undefined, base_url: provider === "custom" ? baseUrl.trim() : undefined, ...(key.trim() ? { api_key: key.trim() } : {}) }, "AI settings saved.");
          }}
        >
          <fieldset disabled={!canEdit} className="grid gap-3 sm:grid-cols-3">
            <legend className="sr-only">Quality</legend>
            {choices.map((c) => (
              <label key={c.id} className={`flex cursor-pointer flex-col gap-1 rounded-xl border-[1.5px] p-4 ${quality === c.id ? "border-ink bg-brand-50" : "border-gray-300 bg-white"} ${canEdit ? "" : "cursor-default opacity-70"}`}>
                <span className="flex items-center gap-2.5 font-bold">
                  <input type="radio" name="quality" checked={quality === c.id} onChange={() => setQuality(c.id)} className="h-[18px] w-[18px] accent-brand-600" />
                  {c.name}
                </span>
                <span className="text-[14px] text-body">{c.about}</span>
              </label>
            ))}
          </fieldset>
          {canEdit ? (
            <>
              <div className="grid gap-4 sm:grid-cols-2">
                <label className={label}>
                  Provider
                  <select value={provider} onChange={(e) => { setProvider(e.target.value); setModel(""); setKey(""); }} className={field}>
                    {saved.providers.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                  </select>
                  <span className={hint}>{own ? "Needs your own key for this provider." : "Wiseflow's key is used unless you add your own."}</span>
                </label>
                <label className={label}>
                  {own ? "Your API key" : "Your own API key (optional)"}
                  <input type="password" value={key} onChange={(e) => setKey(e.target.value)} autoComplete="off" className={`${field} font-mono`}
                    required={own && !(saved.own_key && saved.provider === provider)}
                    placeholder={saved.own_key && saved.provider === provider ? `Saved key ending ${saved.key_ending}` : "Paste the key"} />
                  <span className={hint}>Stored encrypted and never shown again. {own ? "It is tried with one small request before it is saved." : ""}</span>
                </label>
                {provider === "custom" && (
                  <label className={label}>
                    API address
                    <input type="url" required value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} placeholder="https://llm.example.com/v1" className={`${field} font-mono`} />
                    <span className={hint}>Any service that accepts OpenAI-style chat requests.</span>
                  </label>
                )}
                <label className={label}>
                  Model name {provider === "custom" ? "" : "(optional)"}
                  <input value={model} onChange={(e) => setModel(e.target.value)} required={provider === "custom"} maxLength={120} placeholder={suggested || "Exact model name"} className={`${field} font-mono`} />
                  <span className={hint}>
                    {provider === "custom" ? "The exact name the API expects." : `Leave empty to use ${suggested}. Providers rename models often; type the exact name if that one is refused.`}
                  </span>
                </label>
              </div>
              <div className="flex flex-wrap gap-2.5">
                <button type="submit" disabled={busy} className="h-12 rounded-[10px] bg-ink px-5 font-bold text-white disabled:opacity-50">{busy ? "Checking and saving" : "Save AI settings"}</button>
                {saved.own_key && (
                  <button type="button" disabled={busy} onClick={() => save({ quality, provider: "anthropic", api_key: "" }, "Your key was removed. Wiseflow's own key and Claude are used again.")}
                    className="h-12 rounded-[10px] border-[1.5px] border-ink bg-white px-5 font-semibold disabled:opacity-50">
                    Remove my key
                  </button>
                )}
              </div>
            </>
          ) : (
            <p className="text-body">
              Using {saved.providers.find((p) => p.id === saved.provider)?.name ?? "Claude"}{saved.own_key ? " with your organisation's own key" : ""}. An owner or admin can change this.
            </p>
          )}
        </form>
      )}
    </section>
  );
}
