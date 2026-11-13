import { Check } from "lucide-react";

const steps = ["Add your app", "Choose what to test", "Scan runs", "Results"];

/** Where the user is in the four-step scan flow. `current` is 1 to 4. */
export function ScanSteps({ current }: { current: 1 | 2 | 3 | 4 }) {
  return (
    <ol aria-label="Progress" className="flex flex-wrap gap-x-7 gap-y-2 text-sm font-semibold">
      {steps.map((label, i) => {
        const n = i + 1;
        const done = n < current;
        const active = n === current;
        return (
          <li key={label} aria-current={active ? "step" : undefined} className={`flex items-center gap-2 ${done || active ? "text-ink" : "text-body"}`}>
            <span
              className={`flex h-[26px] w-[26px] items-center justify-center rounded-full text-[13px] ${
                done ? "bg-ink text-white" : active ? "bg-brand-600 text-white" : "border-[1.5px] border-gray-400"
              }`}
            >
              {done ? <Check className="h-3.5 w-3.5" strokeWidth={3} aria-label="Done" /> : n}
            </span>
            {label}
          </li>
        );
      })}
    </ol>
  );
}
