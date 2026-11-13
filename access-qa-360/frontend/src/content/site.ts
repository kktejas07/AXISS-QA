/**
 * Facts about the product that are stated in more than one place: on the landing
 * page, in the data search engines read, and in the plain-text summary for AI
 * assistants. Keeping them here means the three can never disagree.
 * Only write what the product really does.
 */
export const site = {
  name: "Wiseflow",
  tagline: "Find what is broken before your customers do.",
  title: "Wiseflow: AI testing and security checks for web, mobile, code and chatbots",
  description:
    "Point Wiseflow at a website, mobile build, repository, API or chatbot. It finds security problems, writes test cases and automation scripts, and tells you what changed since last time.",
  maker: "AXISS Group",
};

/** Questions people ask before trying a testing tool, answered in one or two plain sentences each. */
export const faqs: { q: string; a: string }[] = [
  {
    q: "What is Wiseflow?",
    a: "Wiseflow is an AI testing and security tool. You point it at a website, a mobile build, source code, a repository, an API description or a chatbot, and it reports security problems, writes manual test cases and automation scripts, and shows what changed since the last scan.",
  },
  {
    q: "What can Wiseflow scan?",
    a: "Six things: a website (including pages behind a login), an Android .apk or iOS .ipa build, a .zip of source code, a GitHub, GitLab or Bitbucket repository, an OpenAPI or Swagger file, and your own chatbot's endpoint.",
  },
  {
    q: "Is there a free plan?",
    a: "Yes. The free plan is for one person and allows two scans a month, with no card needed. Team plans add more people and more scans.",
  },
  {
    q: "Does Wiseflow test AI chatbots?",
    a: "Yes. It sends your chatbot the messages an attacker would, such as instructions hidden in content, requests for another customer's details and attempts to reveal its hidden rules, then shows each message, the reply, and whether the bot held.",
  },
  {
    q: "Does Wiseflow run my source code?",
    a: "No. Source code and repositories are read, never run. Wiseflow looks for secrets, risky code and vulnerable packages, and can list every package with its licence.",
  },
  {
    q: "Can Wiseflow scan every pull request or run on a schedule?",
    a: "Yes. Connected to GitHub, it scans each pull request and posts a comment with a pass or fail that only counts what the change added. Scans can also run daily, weekly or monthly, with a message in Slack or Teams saying what is new and what was fixed.",
  },
  {
    q: "Which security standard are findings mapped to?",
    a: "Findings are sorted under the OWASP Top 10, and the mapping can be downloaded as a spreadsheet.",
  },
  {
    q: "Which AI models does Wiseflow use?",
    a: "It uses Claude by default. An organisation can bring its own key for Claude, ChatGPT, Gemini, Grok, Mistral, DeepSeek, Groq, OpenRouter or another OpenAI-compatible service.",
  },
  {
    q: "What do I need to do before scanning something?",
    a: "Only scan what you own or have permission to test. Wiseflow asks you to confirm this before every scan.",
  },
];
