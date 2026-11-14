import { Link } from "react-router-dom";
import { Layout } from "../components/Layout";
import { card, pageTitle } from "../components/ui";

const origin = typeof window === "undefined" ? "https://your-wiseflow-address" : window.location.origin;

export const topics: { id: string; title: string; body: React.ReactNode }[] = [
  {
    id: "first-scan",
    title: "Run your first scan",
    body: (
      <>
        <p>Choose <Link to="/scans/new">New scan</Link>, pick what you are testing, and paste its address or upload its file. On the next screen choose what you want back (a security audit, manual test cases, automation scripts), confirm that you may test it, and start.</p>
        <p>A website scan usually finishes in a few minutes. You can leave the page; the bell at the top of the menu tells you when it is done.</p>
      </>
    ),
  },
  {
    id: "what-you-can-scan",
    title: "What you can scan",
    body: (
      <ul>
        <li><strong>Website:</strong> its address. Add sign-in details to reach pages behind a login; they are deleted when the scan ends.</li>
        <li><strong>Mobile build:</strong> an Android .apk or iOS .ipa file.</li>
        <li><strong>Source code:</strong> a .zip, or a GitHub, GitLab or Bitbucket link. Code is read, never run.</li>
        <li><strong>API:</strong> its OpenAPI or Swagger file.</li>
        <li><strong>Chatbot:</strong> your own assistant's address. Wiseflow sends it the messages an attacker would and shows each reply.</li>
      </ul>
    ),
  },
  {
    id: "results",
    title: "Reading the results",
    body: (
      <>
        <p>Each scan opens on a summary with a risk score from 0 (safest) to 100. The Security tab lists findings by severity with how to fix each one. Changes shows what is new and what was fixed since the last scan of the same target. Standards sorts findings under the OWASP Top 10.</p>
        <p><Link to="/findings">Findings</Link> gathers the open findings from the latest scan of every target. Mark each one fixed, risk accepted or not a problem, and give it an owner. Your decision stays in place on later scans.</p>
      </>
    ),
  },
  {
    id: "schedules",
    title: "Scanning on a timetable or on every pull request",
    body: (
      <>
        <p>Under <Link to="/schedules">Schedules</Link>, pick a target and how often to scan it. After each run you get a message saying what is new and what was fixed.</p>
        <p>Connect GitHub under <Link to="/settings">Settings</Link> to scan each pull request. The result is posted as a comment and a pass or fail that only counts what the change added.</p>
      </>
    ),
  },
  {
    id: "pipeline",
    title: "Starting a scan from your build pipeline",
    body: (
      <>
        <p>An owner or admin creates an API key under <Link to="/settings">Settings</Link>, API keys. A key can start scans and read results; it cannot change settings or people. Send it as a bearer token:</p>
        <pre tabIndex={0}><code>{`curl -X POST ${origin}/api/v1/audits \\
  -H "Authorization: Bearer wf_your_key" \\
  -H "Content-Type: application/json" \\
  -d '{"source_type": "web", "target_url": "https://shop.example.com"}'`}</code></pre>
        <p>The answer includes the scan's <code>id</code>. Read <code>/api/v1/audits/&#123;id&#125;</code> until its status is <code>completed</code>.</p>
      </>
    ),
  },
  {
    id: "wise",
    title: "Asking Wise",
    body: (
      <p>Wise is the round button at the bottom right. It answers from your own scans and the documents you give it under <Link to="/settings">Settings</Link>, and links each answer to where it came from. It can start a scan or add a schedule for you, and always asks before doing so.</p>
    ),
  },
  {
    id: "roles",
    title: "Who can do what",
    body: (
      <ul>
        <li><strong>Owner and Admin:</strong> manage people, connections and settings, and run scans.</li>
        <li><strong>Member:</strong> runs scans and decides what happens to findings.</li>
        <li><strong>Viewer:</strong> reads results and downloads reports.</li>
        <li>The full table is at the bottom of <Link to="/settings">Settings</Link>.</li>
      </ul>
    ),
  },
  {
    id: "safety",
    title: "What Wiseflow does to the thing it scans",
    body: (
      <p>A website scan browses pages and sends test requests the way a careful security tester would. It does not try to take a site down, and it stays on the address you gave. Only scan what you own or have permission to test: you confirm this before every scan.</p>
    ),
  },
];

/** Plain answers to the questions people ask first. */
export function HelpPage() {
  return (
    <Layout>
      <h1 className={pageTitle}>Help</h1>
      <p className="mb-7 mt-1 text-body">How to do the common things in Wiseflow.</p>
      <div className="flex flex-wrap items-start gap-7">
        <nav aria-label="Help topics" className={`${card} flex-[1_1_220px] p-4 lg:sticky lg:top-6 lg:max-w-[260px]`}>
          <ul className="flex flex-col">
            {topics.map((t) => (
              <li key={t.id}>
                <a href={`#${t.id}`} className="block rounded-lg px-3 py-2 text-[15px] font-medium text-body hover:bg-soft hover:text-ink">{t.title}</a>
              </li>
            ))}
          </ul>
        </nav>
        <div className="flex min-w-0 flex-[999_1_480px] flex-col gap-5">
          {topics.map((t) => (
            <section key={t.id} id={t.id} aria-labelledby={`${t.id}-title`} className={`${card} scroll-mt-6 p-6`}>
              <h2 id={`${t.id}-title`} className="mb-2 text-lg font-bold">{t.title}</h2>
              <div className="flex max-w-[68ch] flex-col gap-3 text-[15.5px] leading-relaxed [&_a]:font-semibold [&_a]:text-brand-600 [&_a]:underline [&_code]:font-mono [&_code]:text-[13.5px] [&_li]:ml-5 [&_li]:list-disc [&_pre]:overflow-x-auto [&_pre]:rounded-[10px] [&_pre]:bg-ink [&_pre]:p-4 [&_pre]:text-white [&_ul]:flex [&_ul]:flex-col [&_ul]:gap-1.5">
                {t.body}
              </div>
            </section>
          ))}
        </div>
      </div>
    </Layout>
  );
}
