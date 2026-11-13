import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Layout } from "../components/Layout";
import { createSuite } from "../api/suites";
import { apiError } from "../utils/errors";
import { backLink, card, errorBox, field, hint, label, pageTitle, primaryButton, textarea } from "../components/ui";

export function NewTestPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!projectId) return;
    setError("");
    setSubmitting(true);
    try {
      await createSuite(projectId, { name: name.trim(), feature_description: description.trim() });
      navigate(`/projects/${projectId}/suites`);
    } catch (err) {
      setError(apiError(err, "Could not start writing the tests. Try again."));
      setSubmitting(false);
    }
  };

  return (
    <Layout>
      <Link to={`/projects/${projectId}/suites`} className={backLink}>Test suites</Link>
      <h1 className={`${pageTitle} mb-7 mt-1`}>Generate a test suite</h1>
      <form onSubmit={handleSubmit} className={`${card} flex max-w-2xl flex-col gap-5 p-7`}>
        <label className={label}>
          Suite name
          <input value={name} onChange={(e) => setName(e.target.value)} required maxLength={120} placeholder="Sign-in" className={field} />
        </label>
        <label className={label}>
          What should be tested
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            required
            rows={6}
            placeholder="A user can sign in with a valid email and password and lands on their dashboard. A wrong password shows an error and keeps them on the page."
            className={`${textarea} resize-y`}
          />
          <span className={hint}>Plain words are enough. Wiseflow writes Playwright tests from this with AI; it takes about a minute.</span>
        </label>
        {error && <p role="alert" className={errorBox}>{error}</p>}
        <button type="submit" disabled={submitting} className={`${primaryButton} self-start`}>
          {submitting ? "Starting" : "Generate tests"}
        </button>
      </form>
    </Layout>
  );
}
