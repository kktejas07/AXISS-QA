import { useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, Code2, GitBranch, Globe, Smartphone, Upload } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { Layout } from "../components/Layout";
import { ScanSteps } from "../components/ScanSteps";
import { createDraft, uploadBuild } from "../api/audits";
import type { SourceType } from "../api/audits";
import { useCan } from "../hooks/useMe";
import { apiError } from "../utils/errors";

type Source = "web" | "mobile" | "code" | "repo";

const sources: { id: Source; label: string; hint: string; icon: LucideIcon; ready: boolean }[] = [
  { id: "web", label: "Web app", hint: "Paste a URL", icon: Globe, ready: true },
  { id: "mobile", label: "Mobile build", hint: "Upload an .apk or .ipa", icon: Smartphone, ready: true },
  { id: "code", label: "Source code", hint: "Upload a .zip", icon: Code2, ready: false },
  { id: "repo", label: "Repository", hint: "GitHub, GitLab or Bitbucket", icon: GitBranch, ready: false },
];

const field = "h-[52px] w-full rounded-[10px] border border-gray-400 bg-white px-3.5 text-[15px]";

/** Step 1 of a scan: say what is being tested. Nothing runs until step 2. */
export function NewScanPage() {
  const navigate = useNavigate();
  const [source, setSource] = useState<Source>("web");
  const [url, setUrl] = useState("");
  const [appName, setAppName] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [busy, setBusy] = useState(false);
  const [uploaded, setUploaded] = useState<number | null>(null);
  const [error, setError] = useState("");
  const fileInput = useRef<HTMLInputElement>(null);
  const canScan = useCan("scan.run");

  if (canScan === false) {
    return (
      <Layout>
        <h1 className="mb-4 text-4xl font-extrabold tracking-tight">New scan</h1>
        <p className="max-w-xl rounded-xl border border-gray-300 bg-white px-5 py-4">
          Your role is Viewer, so you can see scans and results but not start new ones. Ask an owner or admin of your
          organisation to make you a member.
        </p>
      </Layout>
    );
  }

  const pickFile = (f: File | undefined) => {
    setError("");
    if (!f) return;
    if (!/\.(apk|ipa)$/i.test(f.name)) {
      setFile(null);
      setError("Choose an Android .apk or an iOS .ipa file.");
      return;
    }
    setFile(f);
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (source === "mobile" && !file) {
      setError("Choose the app build to upload.");
      return;
    }
    setBusy(true);
    try {
      const name = appName.trim() || undefined;
      if (source === "web") {
        const { data } = await createDraft({ source_type: "web", target_url: url.trim(), app_name: name });
        navigate(`/audits/${data.id}/setup`);
      } else if (file) {
        const type: SourceType = /\.ipa$/i.test(file.name) ? "ios" : "android";
        const { data } = await createDraft({ source_type: type, app_name: name });
        setUploaded(0);
        await uploadBuild(data.id, file, setUploaded);
        navigate(`/audits/${data.id}/setup`);
      }
    } catch (err) {
      setError(apiError(err, "Could not save this app. Check your connection and try again."));
      setUploaded(null);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Layout>
      <div className="mb-7 flex flex-col gap-5">
        <h1 className="text-4xl font-extrabold tracking-tight">What are we testing?</h1>
        <ScanSteps current={1} />
      </div>

      <form onSubmit={submit} className="flex max-w-3xl flex-col gap-6">
        <div role="group" aria-label="Type of app" className="grid gap-3.5 sm:grid-cols-2 lg:grid-cols-4">
          {sources.map(({ id, label, hint, icon: Icon, ready }) => {
            const on = source === id;
            return (
              <button
                key={id}
                type="button"
                disabled={!ready}
                aria-pressed={on}
                onClick={() => {
                  setSource(id);
                  setError("");
                }}
                className={`flex flex-col gap-2.5 rounded-[14px] border-2 bg-white p-[18px] text-left disabled:cursor-not-allowed disabled:opacity-60 ${
                  on ? "border-ink shadow-[5px_5px_0_#3b30e0]" : "border-gray-300"
                }`}
              >
                <Icon className={`h-6 w-6 ${on ? "text-brand-600" : "text-body"}`} aria-hidden="true" />
                <span className="font-bold">{label}</span>
                <span className="text-[13.5px] text-body">{ready ? hint : "Not available yet"}</span>
              </button>
            );
          })}
        </div>

        <div className="flex flex-col gap-5 rounded-2xl border border-gray-300 bg-white p-7">
          {source === "web" ? (
            <label className="flex flex-col gap-2 font-semibold">
              Web app address
              <input
                type="url"
                required
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://your-app.com"
                className={`${field} font-mono font-normal`}
              />
              <span className="text-[13.5px] font-normal text-body">
                Security checks send test requests to this address. Use a staging or test site when you can.
              </span>
            </label>
          ) : (
            <div className="flex flex-col gap-2">
              <div
                onDragOver={(e) => {
                  e.preventDefault();
                  setDragging(true);
                }}
                onDragLeave={() => setDragging(false)}
                onDrop={(e) => {
                  e.preventDefault();
                  setDragging(false);
                  pickFile(e.dataTransfer.files[0]);
                }}
                className={`flex flex-col items-center gap-3 rounded-[14px] border-2 border-dashed px-6 py-10 text-center ${
                  dragging ? "border-brand-600 bg-brand-50" : "border-gray-400 bg-soft"
                }`}
              >
                <Upload className="h-8 w-8 text-brand-600" aria-hidden="true" />
                <span className="text-lg font-bold">{file ? file.name : "Drop your build here"}</span>
                <span className="text-body">
                  {file ? `${(file.size / 1024 / 1024).toFixed(1)} MB` : "Android .apk or iOS .ipa"}
                </span>
                <input
                  ref={fileInput}
                  id="build-file"
                  type="file"
                  accept=".apk,.ipa"
                  className="sr-only"
                  onChange={(e) => pickFile(e.target.files?.[0])}
                />
                <label
                  htmlFor="build-file"
                  className="flex h-12 cursor-pointer items-center rounded-[10px] border-[1.5px] border-ink bg-white px-5 font-semibold focus-within:outline focus-within:outline-2"
                >
                  {file ? "Choose a different file" : "Choose file"}
                </label>
              </div>
              {uploaded !== null && (
                <div role="progressbar" aria-valuenow={uploaded} aria-valuemin={0} aria-valuemax={100} aria-label="Upload progress" className="h-2 overflow-hidden rounded-full bg-line">
                  <div className="h-full bg-brand-600" style={{ width: `${uploaded}%` }} />
                </div>
              )}
            </div>
          )}

          <label className="flex flex-col gap-2 font-semibold">
            App name <span className="sr-only">(optional)</span>
            <input
              type="text"
              value={appName}
              onChange={(e) => setAppName(e.target.value)}
              placeholder="Optional, shown in your scan list"
              maxLength={120}
              className={`${field} max-w-md font-normal`}
            />
          </label>

          {error && (
            <p role="alert" className="rounded-[10px] border border-red-200 bg-red-50 px-4 py-3 text-red-800">
              {error}
            </p>
          )}

          <div className="flex flex-wrap items-center justify-between gap-4 border-t border-line pt-5">
            <span className="text-[13.5px] text-body">Nothing is tested until you confirm on the next step.</span>
            <button
              type="submit"
              disabled={busy}
              className="flex h-[52px] items-center gap-2 rounded-[10px] bg-brand-600 px-6 font-bold text-white hover:bg-brand-700 disabled:opacity-60"
            >
              {busy ? (uploaded !== null ? `Uploading, ${uploaded}%` : "Saving") : "Continue"}
              {!busy && <ArrowRight className="h-[18px] w-[18px]" strokeWidth={2.4} aria-hidden="true" />}
            </button>
          </div>
        </div>

        <p className="text-[13.5px] text-body">
          Only need a quick OWASP check of one URL?{" "}
          <Link to="/scans/quick" className="font-semibold text-brand-600 hover:text-brand-700">
            Run a quick security scan
          </Link>
        </p>
      </form>
    </Layout>
  );
}
