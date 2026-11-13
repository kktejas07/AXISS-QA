const labels: Record<string, string> = {
  queued: "Queued",
  running: "Running",
  crawling: "Crawling",
  scanning: "Scanning",
  analyzing: "Analysing",
  completed: "Completed",
  partial: "Finished with errors",
  failed: "Failed",
  draft: "Not started",
};

const inProgress = new Set(["running", "crawling", "scanning", "analyzing"]);

function tone(status: string): string {
  if (status === "completed") return "bg-emerald-100 text-emerald-800";
  if (status === "failed") return "bg-red-100 text-red-800";
  if (status === "partial") return "bg-orange-100 text-orange-900";
  if (status === "queued" || status === "draft") return "bg-gray-100 text-gray-700";
  return "bg-brand-50 text-brand-700";
}

/** Status of a scan from either engine, with its percentage while it is running. */
export function StatusPill({ status, progress }: { status: string; progress?: number }) {
  return (
    <span className={`inline-block whitespace-nowrap rounded-full px-2.5 py-1 text-[13px] font-bold ${tone(status)}`}>
      {labels[status] ?? status}
      {inProgress.has(status) && progress !== undefined ? `, ${progress}%` : ""}
    </span>
  );
}
