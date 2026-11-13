/** The app's loader: the Wiseflow "W" drawing itself, with three dots below. Still for people who prefer reduced motion. */
export function LoadingSpinner({ label = "Loading" }: { label?: string }) {
  return (
    <div role="status" aria-label={label} className="flex flex-col items-center justify-center gap-3 py-12">
      <svg viewBox="0 0 64 64" className="h-12 w-12" fill="none" aria-hidden="true">
        <path d="M8 14l12 36 12-24 12 24 12-36" stroke="#e0e7ff" strokeWidth="7" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M8 14l12 36 12-24 12 24 12-36" stroke="#4338ca" strokeWidth="7" strokeLinecap="round" strokeLinejoin="round" className="wf-draw" />
      </svg>
      <Dots />
    </div>
  );
}

/** Three dots that rise in turn: something is being worked on. */
export function Dots({ className = "bg-brand-600" }: { className?: string }) {
  return (
    <span className="flex items-center gap-1.5" aria-hidden="true">
      {[0, 1, 2].map((i) => (
        <span key={i} className={`wf-dot h-2 w-2 rounded-full ${className}`} style={{ animationDelay: `${i * 0.15}s` }} />
      ))}
    </span>
  );
}

/** Grey placeholder bars shaped like the content that is on its way. */
export function Skeleton({ rows = 3, className = "" }: { rows?: number; className?: string }) {
  return (
    <div role="status" aria-label="Loading" className={`flex flex-col gap-3 ${className}`}>
      {Array.from({ length: rows }, (_, i) => (
        <span key={i} className="wf-skeleton block h-4" style={{ width: `${[92, 78, 60, 85, 70][i % 5]}%` }} />
      ))}
    </div>
  );
}
