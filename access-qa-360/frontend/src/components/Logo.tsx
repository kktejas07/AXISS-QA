/**
 * The Wiseflow mark and wordmark, from the brand files in public/brand.
 * `reversed` is for dark backgrounds.
 */
const W = "M4 10h12l8 28 8-18 8 18 8-28h12L46 54H38l-6-14-6 14h-8z";

export function LogoMark({ size = 30, reversed = false }: { size?: number; reversed?: boolean }) {
  const id = reversed ? "wf-right-reversed" : "wf-right";
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" aria-hidden="true" className="flex-none">
      <defs>
        <clipPath id={id}>
          <rect x="32" y="0" width="32" height="64" />
        </clipPath>
      </defs>
      <path d={W} fill={reversed ? "#fff" : "#3730a3"} />
      <path d={W} fill={reversed ? "#a5b4fc" : "#818cf8"} clipPath={`url(#${id})`} />
    </svg>
  );
}

export function Logo({ reversed = false }: { reversed?: boolean }) {
  return (
    <span className="flex items-center gap-2">
      <LogoMark reversed={reversed} />
      <span className={`font-brand text-[23px] font-semibold leading-none tracking-[-0.02em] ${reversed ? "text-white" : "text-brand-950"}`}>Wiseflow</span>
    </span>
  );
}
