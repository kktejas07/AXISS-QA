import { Link } from "react-router-dom";
import { Logo } from "../components/Logo";

// Starting text only. It describes what the product does with data as built, but it has not been
// reviewed by a lawyer and names no company or country. Replace it before launch.
const pages = {
  privacy: {
    title: "Privacy",
    sections: [
      ["What we collect", "Your name, email address and a hashed password when you create an account. What you ask Wiseflow to test: web addresses, uploaded builds and code, API descriptions and chatbot endpoints. The results of those scans. Documents you upload for Wise."],
      ["How it is used", "To run the scans you start, show you the results, and answer your questions in Wise. Parts of a scan are sent to an AI provider to write test cases, scripts and summaries: Anthropic by default, or the provider whose key your organisation adds in Settings."],
      ["What we do not keep", "Uploaded source code is deleted when its scan finishes. Sign-in details and keys you give for a scan are stored encrypted and deleted when the scan ends."],
      ["Who can see it", "People in your organisation, according to their role. Wiseflow staff with administrator access can see accounts and scans to support the service."],
      ["Your choices", "You can ask for your account and its data to be deleted, or for a copy of it, by contacting us."],
    ],
  },
  terms: {
    title: "Terms",
    sections: [
      ["Only test what you may test", "Before each scan you confirm that you own the app or have permission to test it. Do not use Wiseflow against systems you are not allowed to test."],
      ["Your account", "Keep your password and any API keys private. You are responsible for what is done with them."],
      ["What a scan is and is not", "A scan reports what its checks found at the time it ran. An empty result does not mean an app is secure, and Wiseflow is not a certification."],
      ["Plans and limits", "Each plan has a number of people and scans per month. Paid plans renew until cancelled; you can cancel in Settings."],
      ["Changes", "These terms may be updated. We will say so in the product when they are."],
    ],
  },
} as const;

/** Privacy and terms. Draft text, marked as such on the page until it has been reviewed. */
export function LegalPage({ kind }: { kind: keyof typeof pages }) {
  const page = pages[kind];
  return (
    <div className="min-h-screen bg-white font-sans text-ink">
      <header className="mx-auto flex w-full max-w-3xl items-center justify-between px-5 py-5">
        <Link to="/" aria-label="Wiseflow, home"><Logo /></Link>
        <Link to="/" className="font-semibold text-brand-600">Home</Link>
      </header>
      <main className="mx-auto w-full max-w-3xl px-5 pb-16">
        <h1 className="text-4xl font-extrabold tracking-tight">{page.title}</h1>
        <p role="note" className="mt-4 rounded-[10px] border border-amber-300 bg-amber-50 px-4 py-3 text-amber-900">
          This is a draft. It has not been reviewed by a lawyer and must be replaced before Wiseflow is offered to customers.
        </p>
        <div className="mt-8 flex flex-col gap-7">
          {page.sections.map(([heading, text]) => (
            <section key={heading}>
              <h2 className="text-xl font-bold">{heading}</h2>
              <p className="mt-1.5 max-w-[68ch] text-body">{text}</p>
            </section>
          ))}
        </div>
      </main>
    </div>
  );
}
