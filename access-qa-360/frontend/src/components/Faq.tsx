import { useId, useState } from "react";
import { ChevronDown } from "lucide-react";

/**
 * Questions that open and close. One is open at a time; the first starts open.
 * Every answer stays in the page while closed, so search engines and "find in page"
 * still read it; it is only hidden from sight and from screen readers until opened.
 */
export function Faq({ items, level = 3 }: { items: { q: string; a: string }[]; level?: 2 | 3 }) {
  const [open, setOpen] = useState<number | null>(0);
  const id = useId();
  const Heading = `h${level}` as "h2" | "h3";
  return (
    <div className="flex flex-col divide-y divide-line overflow-hidden rounded-2xl border border-gray-300 bg-white">
      {items.map((item, i) => {
        const shown = open === i;
        return (
          <div key={item.q}>
            <Heading>
              <button
                type="button"
                aria-expanded={shown}
                aria-controls={`${id}-${i}`}
                onClick={() => setOpen(shown ? null : i)}
                className="flex min-h-[64px] w-full items-center justify-between gap-4 px-6 py-4 text-left text-lg font-bold hover:bg-soft"
              >
                {item.q}
                <span className={`flex h-9 w-9 flex-none items-center justify-center rounded-full border-[1.5px] border-ink transition-transform duration-300 motion-reduce:transition-none ${shown ? "rotate-180 bg-ink text-white" : "bg-white"}`}>
                  <ChevronDown className="h-5 w-5" aria-hidden="true" />
                </span>
              </button>
            </Heading>
            {/* The row grows from nothing to the answer's own height, so the drop is smooth whatever its length. */}
            <div
              id={`${id}-${i}`}
              role="region"
              aria-label={item.q}
              className="faq-drop grid motion-reduce:transition-none"
              style={{ gridTemplateRows: shown ? "1fr" : "0fr", visibility: shown ? "visible" : "hidden" }}
            >
              <div className="overflow-hidden">
                <p className={`max-w-[68ch] px-6 pb-5 text-body transition-[opacity,transform] duration-300 motion-reduce:transition-none ${shown ? "translate-y-0 opacity-100" : "-translate-y-1.5 opacity-0"}`}>{item.a}</p>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
