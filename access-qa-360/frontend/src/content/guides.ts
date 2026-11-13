/**
 * Public guides: short, practical explanations of the problems Wiseflow works on.
 * They are written to be useful on their own, and each one says plainly where the
 * product fits. Keep every statement true and checkable; these pages are read by
 * people, search engines and AI assistants alike.
 */
export interface Guide {
  slug: string;
  title: string;
  description: string;
  updated: string;          // YYYY-MM-DD
  minutes: number;
  sections: { heading: string; paragraphs?: string[]; points?: string[] }[];
}

export const guides: Guide[] = [
  {
    slug: "test-a-chatbot-for-prompt-injection",
    title: "How to test a chatbot for prompt injection",
    description: "What prompt injection is, the kinds of message to try against your own AI assistant, and how to judge whether it held.",
    updated: "2026-11-14",
    minutes: 5,
    sections: [
      {
        heading: "What prompt injection is",
        paragraphs: [
          "A chatbot built on a language model follows instructions written in plain language. Prompt injection is when someone other than you gets their own instructions in front of the model, and the model follows them instead of yours.",
          "It comes in two forms. In direct injection, the person typing tells the bot to ignore its rules. In indirect injection, the instructions are hidden in something the bot reads on the user's behalf: a web page, an email, a document, a product review.",
        ],
      },
      {
        heading: "What to try against your own bot",
        paragraphs: ["Test only a bot you own or have permission to test. A useful first round covers these:"],
        points: [
          "Ask it to ignore its previous instructions and do something harmless but out of character, such as replying with a fixed code word.",
          "Ask it to repeat or summarise its hidden instructions (the system prompt).",
          "Ask for another customer's details, as if you were a colleague or the account owner.",
          "Paste in content that contains an instruction (\"when you summarise this, also say…\") and see whether the bot obeys the content or only summarises it.",
          "Ask it to act outside its job: give medical or legal advice, write code, or speak for the company on something it was never meant to cover.",
          "Send the same request reworded, in another language, or wrapped in a role-play, to see whether a refusal holds.",
        ],
      },
      {
        heading: "How to judge the replies",
        paragraphs: [
          "Decide what \"held\" means before you start, so you are not grading on feel. A canary helps: tell the test message to reply with a specific code, then check whether that code appears. If it does, the bot followed the injected instruction.",
          "Some replies cannot be judged by a simple rule, for example whether a piece of advice was out of scope. Mark those for a person to read rather than guessing.",
          "Run the same set again after every change to the prompt, the model or the tools the bot can call. A fix for one message often opens another.",
        ],
      },
      {
        heading: "Where Wiseflow fits",
        paragraphs: [
          "A Wiseflow chatbot scan sends your endpoint a fixed set of these messages, shows each message with the bot's reply, marks which ones the bot failed, and flags the replies that need a person to judge. The endpoint must be a public https address, and any key you give for the scan is deleted when it ends.",
        ],
      },
    ],
  },
  {
    slug: "owasp-top-10-in-plain-words",
    title: "The OWASP Top 10 in plain words",
    description: "The ten categories of web application security risk in the OWASP Top 10 (2021), each explained in a sentence, and how to use the list.",
    updated: "2026-11-14",
    minutes: 6,
    sections: [
      {
        heading: "What the list is",
        paragraphs: [
          "The OWASP Top 10 is a list of the most significant categories of security risk in web applications, published by the Open Worldwide Application Security Project, a non-profit. The 2021 edition is the one most audits and customer questionnaires refer to. It is a way of grouping problems, not a complete test plan.",
        ],
      },
      {
        heading: "The ten categories (2021)",
        points: [
          "A01 Broken access control: people can see or change things they should not, such as another customer's order.",
          "A02 Cryptographic failures: sensitive data is sent or stored without proper encryption.",
          "A03 Injection: input from a user is treated as a command, as in SQL injection and cross-site scripting.",
          "A04 Insecure design: the feature is risky by design, so no amount of careful coding fixes it.",
          "A05 Security misconfiguration: default passwords, debug pages left on, missing security headers.",
          "A06 Vulnerable and outdated components: a library you depend on has a known flaw.",
          "A07 Identification and authentication failures: weak sign-in, such as no limit on password guesses.",
          "A08 Software and data integrity failures: code or updates are trusted without checking where they came from.",
          "A09 Security logging and monitoring failures: an attack happens and nothing records it.",
          "A10 Server-side request forgery: the server can be told to fetch an address of the attacker's choosing, often inside your own network.",
        ],
      },
      {
        heading: "How to use it",
        paragraphs: [
          "Sort your findings under the ten categories and look at where they cluster. Many findings under A05 usually means deployment settings need a checklist. Many under A01 means access rules need tests of their own.",
          "When a customer or auditor asks whether you cover the OWASP Top 10, they usually want to see that findings are tracked against it and that each has an owner and a status.",
        ],
      },
      {
        heading: "Where Wiseflow fits",
        paragraphs: [
          "Every Wiseflow scan has a Standards view that sorts its findings under the OWASP Top 10, and the mapping can be downloaded as a spreadsheet for whoever asks.",
        ],
      },
    ],
  },
  {
    slug: "what-is-an-sbom",
    title: "What a software bill of materials (SBOM) is, and when you need one",
    description: "What an SBOM contains, the two common formats, who asks for one, and how to produce it from your code.",
    updated: "2026-11-14",
    minutes: 4,
    sections: [
      {
        heading: "What it is",
        paragraphs: [
          "A software bill of materials is a list of every package your product is built from, with exact versions. It is the software equivalent of an ingredients label.",
          "Its value shows the day a serious flaw is announced in a popular library. With an SBOM you can answer \"are we affected?\" by searching a file, instead of asking every team.",
        ],
      },
      {
        heading: "The two common formats",
        points: [
          "CycloneDX, an OWASP project, designed with security use in mind.",
          "SPDX, a Linux Foundation project and an ISO standard, which began with licence compliance.",
        ],
      },
      {
        heading: "Who asks for one",
        paragraphs: [
          "Larger customers ask for an SBOM in security questionnaires and contracts, and suppliers to government are increasingly required to provide one. Even if nobody has asked yet, producing one on every release costs little and saves time when the question comes.",
        ],
      },
      {
        heading: "How to produce a good one",
        points: [
          "Build it from lock files, which record exact versions, not from the loose ranges in a manifest.",
          "Include the packages your packages depend on, not only the ones you chose yourself.",
          "Produce it automatically on each release, so it never describes last quarter's code.",
          "Keep the file with the release it describes.",
        ],
      },
      {
        heading: "Where Wiseflow fits",
        paragraphs: [
          "A Wiseflow code or repository scan lists the packages it finds with exact versions and offers them as a CycloneDX file on the scan's Downloads tab. The same scan checks those packages for known vulnerabilities.",
        ],
      },
    ],
  },
  {
    slug: "open-source-licences-that-affect-your-product",
    title: "Open-source licences: which ones can affect your product",
    description: "The three broad groups of open-source licence, what each asks of you when you ship a product, and what to do about packages with no licence.",
    updated: "2026-11-14",
    minutes: 5,
    sections: [
      {
        heading: "Why it matters",
        paragraphs: [
          "Almost every product is built on open-source packages, and each comes with a licence that says what you may do with it. Most ask for very little. A few ask for a lot. This guide shows where to look; it is not legal advice, and a lawyer should decide anything that matters to your business.",
        ],
      },
      {
        heading: "Three broad groups",
        points: [
          "Permissive (MIT, Apache 2.0, BSD, ISC): you may use the package in a closed product. Keep the copyright notice and licence text.",
          "Weak copyleft (LGPL, MPL, EPL): if you change the package itself, you share those changes. Your own code can stay closed.",
          "Strong copyleft (GPL, AGPL): if you distribute a product that includes the package, you may be required to release your own source code under the same licence. AGPL extends this to software offered over a network.",
        ],
      },
      {
        heading: "Packages with no licence",
        paragraphs: [
          "A package with no licence is not free to use. Without a licence, the author keeps all rights by default. Treat these as needing a decision: find the licence, ask the author, or replace the package.",
        ],
      },
      {
        heading: "A sensible routine",
        points: [
          "List the licence of every package, including the ones your packages depend on.",
          "Look first at strong copyleft and at packages with no licence.",
          "Where a package offers a choice (\"MIT OR GPL\"), you may pick the one that suits you.",
          "Check again when dependencies change, not once a year.",
        ],
      },
      {
        heading: "Where Wiseflow fits",
        paragraphs: [
          "A Wiseflow code scan can look up the licence of each Python and JavaScript package it found and list first the ones that may require sharing your code or that have no licence. Other kinds of package are reported as not covered.",
        ],
      },
    ],
  },
  {
    slug: "security-scans-on-every-pull-request",
    title: "Running a security scan on every pull request",
    description: "Why to scan each change before it merges, how to stop the check from blocking on old problems, and what a useful result looks like.",
    updated: "2026-11-14",
    minutes: 4,
    sections: [
      {
        heading: "Why scan each change",
        paragraphs: [
          "A problem is cheapest to fix while the person who wrote it still has the change open. A scan once a quarter finds the same problem months later, mixed in with hundreds of others, when nobody remembers why the code is the way it is.",
        ],
      },
      {
        heading: "Judge the change, not the history",
        paragraphs: [
          "The usual reason teams switch a pull request check off is that it fails on problems that were already there. The fix is to compare the scan of the branch with the last scan of the main branch, and fail only on what the change added.",
          "Old problems still matter, but they belong in a list with owners and dates, not in the way of every unrelated change.",
        ],
      },
      {
        heading: "What a useful result looks like",
        points: [
          "A comment on the pull request that names each new finding and how to fix it.",
          "A pass or fail status that counts only new critical and high findings.",
          "A note of what the change fixed, so good work is visible too.",
          "A way to mark a finding as accepted or not a problem, with a reason, that later scans remember.",
        ],
      },
      {
        heading: "Where Wiseflow fits",
        paragraphs: [
          "Connected to GitHub, Wiseflow scans the branch of each pull request, posts a comment and a pass or fail that only counts what the change added. Decisions made in its findings list carry over to later scans.",
        ],
      },
    ],
  },
];

export const guide = (slug: string) => guides.find((g) => g.slug === slug);
