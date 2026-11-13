import { useEffect, useState } from "react";
import { CheckCircle2, CircleSlash, KeyRound, XCircle } from "lucide-react";
import { Layout } from "../components/Layout";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { getPlatform, savePlatform, testPlatform } from "../api/admin";
import type { PlatformField, PlatformGroup, PlatformPage } from "../api/admin";
import { card, errorBox, field as input, hint, pageTitle, primaryButton, quietButton } from "../components/ui";
import { apiError } from "../utils/errors";

function Status({ group }: { group: PlatformGroup }) {
  const last = group.last_check;
  const [Icon, text, look] = !group.configured
    ? [CircleSlash, "Not set up", "bg-soft text-body"] as const
    : last?.ok === false
      ? [XCircle, "Last test failed", "bg-red-100 text-red-800"] as const
      : last?.ok
        ? [CheckCircle2, "Last test passed", "bg-emerald-100 text-emerald-900"] as const
        : [KeyRound, "Set, not tested", "bg-amber-100 text-amber-900"] as const;
  return (
    <span className={`flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-1 text-[13px] font-bold ${look}`}>
      <Icon className="h-4 w-4" aria-hidden="true" /> {text}
    </span>
  );
}

const where = (f: PlatformField) => (f.source === "console" ? "saved here" : "from the server's own settings");

function Group({ group, providers, onChange }: { group: PlatformGroup; providers: PlatformPage["providers"]; onChange: (page: PlatformPage) => void }) {
  // Only what the admin typed. Secrets start empty, because the saved key is never sent to the browser.
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<"" | "save" | "test">("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const shown = (f: PlatformField) => draft[f.key] ?? (f.secret ? "" : f.value ?? "");
  const changes = Object.fromEntries(group.fields.filter((f) => f.key in draft && (f.secret ? draft[f.key].trim() !== "" : draft[f.key].trim() !== (f.value ?? ""))).map((f) => [f.key, draft[f.key]]));
  const dirty = Object.keys(changes).length > 0;

  const run = async (kind: "save" | "test", work: () => Promise<string>) => {
    setError("");
    setNotice("");
    setBusy(kind);
    try {
      setNotice(await work());
    } catch (e) {
      setError(apiError(e, kind === "save" ? "The change could not be saved." : "The test could not be run."));
    } finally {
      setBusy("");
    }
  };
  const save = (values: Record<string, string>, done: string) =>
    run("save", async () => {
      onChange((await savePlatform(values)).data);
      setDraft({});
      return done;
    });
  const test = () =>
    run("test", async () => {
      const result = (await testPlatform(group.id)).data;
      onChange((await getPlatform()).data);
      if (result.ok === false) {
        setError(result.detail);
        return "";
      }
      return result.detail;
    });

  return (
    <section aria-labelledby={`keys-${group.id}`} className={`${card} p-6`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-[1_1_320px]">
          <h2 id={`keys-${group.id}`} className="text-lg font-bold">{group.title}</h2>
          <p className="text-body">{group.about}</p>
        </div>
        <Status group={group} />
      </div>

      <form
        className="mt-5 flex flex-col gap-4"
        onSubmit={(e) => {
          e.preventDefault();
          save(changes, "Saved. It is in use from now.");
        }}
      >
        <div className="grid gap-4 sm:grid-cols-2">
          {group.fields.map((f) => (
            <div key={f.key} className="flex flex-col gap-1.5">
              <label htmlFor={`f-${f.key}`} className="text-sm font-semibold">{f.label}</label>
              {f.key === "DEFAULT_AI_PROVIDER" ? (
                <select id={`f-${f.key}`} value={shown(f)} onChange={(e) => setDraft({ ...draft, [f.key]: e.target.value })} className={`${input} px-2.5`}>
                  {providers.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                </select>
              ) : (
                <input
                  id={`f-${f.key}`}
                  aria-describedby={`h-${f.key}`}
                  type={f.secret ? "password" : "text"}
                  autoComplete="off"
                  spellCheck={false}
                  value={shown(f)}
                  onChange={(e) => setDraft({ ...draft, [f.key]: e.target.value })}
                  placeholder={f.secret ? (f.set ? "Type a new one to replace it" : "Not set") : "Not set"}
                  className={`${input} font-mono`}
                />
              )}
              <span id={`h-${f.key}`} className={hint}>
                {f.secret
                  ? f.set ? `A key is set (${f.hint}), ${where(f)}. It is never shown in full.` : "No key is set."
                  : f.set ? `In use, ${where(f)}.` : "Nothing is set."}
                {f.source === "console" && f.key !== "DEFAULT_AI_PROVIDER" && (
                  <>
                    {" "}
                    <button type="button" disabled={busy !== ""} onClick={() => save({ [f.key]: "" }, `${f.label} removed. The server's own value applies again.`)} className="font-semibold text-brand-600 underline hover:text-brand-700">
                      Remove<span className="sr-only"> {f.label}</span>
                    </button>
                  </>
                )}
              </span>
            </div>
          ))}
        </div>

        {error && <p role="alert" className={errorBox}>{error}</p>}
        {notice && <p role="status" className="rounded-[10px] border border-emerald-200 bg-emerald-50 px-4 py-3 text-emerald-900">{notice}</p>}
        {group.last_check && !error && !notice && (
          <p className="text-[14.5px] text-body">
            Last test, {new Date(group.last_check.at).toLocaleString()}: {group.last_check.detail}
          </p>
        )}

        <div className="flex flex-wrap gap-3">
          <button type="submit" disabled={!dirty || busy !== ""} className={primaryButton}>{busy === "save" ? "Saving" : `Save ${group.title}`}</button>
          <button type="button" onClick={test} disabled={!group.configured || dirty || busy !== ""} className={quietButton}>{busy === "test" ? "Testing" : `Test ${group.title}`}</button>
        </div>
      </form>
    </section>
  );
}

/** Super admin: the platform's own keys. They can be replaced and tested here, and are never shown in full. */
export function AdminKeysPage() {
  const [page, setPage] = useState<PlatformPage | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    getPlatform().then((r) => setPage(r.data)).catch(() => setFailed(true));
  }, []);

  return (
    <Layout variant="admin">
      <h1 className={pageTitle}>Platform keys</h1>
      <p className="mb-7 mt-1 max-w-3xl text-body">
        The keys Wiseflow itself uses. A value saved here replaces the one in the server's settings straight away, is stored encrypted,
        and every change is written to the audit log. Testing makes one small real call.
      </p>
      {failed ? (
        <p role="alert" className={errorBox}>Platform keys could not be loaded. Reload the page to try again.</p>
      ) : !page ? (
        <LoadingSpinner />
      ) : (
        <div className="flex flex-col gap-6">
          {page.groups.map((g) => <Group key={g.id} group={g} providers={page.providers} onChange={setPage} />)}
        </div>
      )}
    </Layout>
  );
}
