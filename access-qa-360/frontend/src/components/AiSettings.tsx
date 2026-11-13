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

/** Which AI model this organisation's scans and Wise use, and whose key pays for it. */
export function AiSettingsSection({ canEdit }: { canEdit: boolean }) {
  const [saved, setSaved] = useState<AiSettings | null>(null);
  const [quality, setQuality] = useState<AiSettings["quality"]>("balanced");
  const [key, setKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    getAiSettings().then((r) => { setSaved(r.data); setQuality(r.data.quality); }).catch(() => setError("The AI settings could not be loaded."));
  }, []);

  const save = async (body: Parameters<typeof saveAiSettings>[0], done: string) => {
    setError("");
    setNotice("");
    setBusy(true);
    try {
      const { data } = await saveAiSettings(body);
      setSaved(data);
      setQuality(data.quality);
      setKey("");
      setNotice(done);
    } catch (e) {
      setError(apiError(e, "The AI settings could not be saved."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="rounded-2xl border border-gray-300 bg-white p-6">
      <h2 className="text-lg font-bold">AI model</h2>
      <p className="mb-4 max-w-[66ch] text-body">Choose speed against quality for the test cases, scripts and summaries Wiseflow writes, and for Wise's answers.</p>
      {error && <p role="alert" className={`${errorBox} mb-4`}>{error}</p>}
      {notice && <p role="status" className="mb-4 rounded-[10px] border border-emerald-200 bg-emerald-50 px-4 py-3 text-emerald-900">{notice}</p>}
      {saved && (
        <form className="flex flex-col gap-5" onSubmit={(e) => { e.preventDefault(); save({ quality, ...(key.trim() ? { api_key: key.trim() } : {}) }, "AI settings saved."); }}>
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
              <label className={`${label} max-w-[520px]`}>
                Your own Anthropic API key (optional)
                <input type="password" value={key} onChange={(e) => setKey(e.target.value)} autoComplete="off" placeholder={saved.own_key ? `Saved key ending ${saved.key_ending}` : "sk-ant-…"} className={`${field} font-mono`} />
                <span className={hint}>
                  {saved.own_key ? "AI work for this organisation is billed to your key. Enter a new one to replace it." : "Without one, Wiseflow's own key is used. With one, AI work for this organisation is billed to you. It is stored encrypted and never shown again."}
                </span>
              </label>
              <div className="flex flex-wrap gap-2.5">
                <button type="submit" disabled={busy} className="h-12 rounded-[10px] bg-ink px-5 font-bold text-white disabled:opacity-50">{busy ? "Saving" : "Save AI settings"}</button>
                {saved.own_key && (
                  <button type="button" disabled={busy} onClick={() => save({ quality, api_key: "" }, "Your key was removed. Wiseflow's key is used again.")} className="h-12 rounded-[10px] border-[1.5px] border-ink bg-white px-5 font-semibold disabled:opacity-50">
                    Remove my key
                  </button>
                )}
              </div>
            </>
          ) : (
            <p className="text-body">An owner or admin of your organisation can change this.</p>
          )}
        </form>
      )}
    </section>
  );
}
