import { useEffect, useRef, useState } from "react";
import { WiseOwl } from "./Illustrations";

/** What Wise is doing. Each has its own looping animation. */
export type BotState = "idle" | "working" | "typing" | "thinking" | "reading" | "writing" | "designing" | "coding" | "searching" | "listening" | "sleeping" | "done" | "error";

const files = new Map<string, Promise<object | null>>();

/**
 * One animation file, fetched once. The files are licensed artwork that is installed on the
 * server rather than kept in the repository, so they may not be there: then this gives null.
 */
export function loadBot(state: BotState): Promise<object | null> {
  if (!files.has(state)) {
    files.set(
      state,
      fetch(`${import.meta.env.BASE_URL}wise-bot/${state}.json`)
        // A missing file comes back as the app's own page, so the type is checked as well as the status.
        .then((r) => (r.ok && (r.headers.get("content-type") ?? "").includes("json") ? r.json() : null))
        .then((data) => (data && Array.isArray((data as { layers?: unknown }).layers) ? data : null))
        .catch(() => null),
    );
  }
  return files.get(state)!;
}

const still = () => typeof window.matchMedia === "function" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/**
 * Wise as an animated character whose movement shows what it is doing. Decorative: the text
 * next to it says the same thing. Falls back to the drawn owl when the animations are not installed.
 */
export function WiseBot({ state = "idle", className = "h-12 w-12" }: { state?: BotState; className?: string }) {
  const box = useRef<HTMLDivElement>(null);
  const [missing, setMissing] = useState(false);

  useEffect(() => {
    let stopped = false;
    let animation: { destroy: () => void } | undefined;
    Promise.all([loadBot(state), import("lottie-web/build/player/lottie_light")])
      .then(([data, lottie]) => {
        if (stopped) return;
        if (!data || !box.current) return setMissing(!data);
        setMissing(false);
        const reduced = still();
        const player = lottie.default.loadAnimation({ container: box.current, renderer: "svg", loop: !reduced, autoplay: !reduced, animationData: structuredClone(data) });
        if (reduced) player.goToAndStop(40, true);
        animation = player;
      })
      .catch(() => !stopped && setMissing(true));
    return () => {
      stopped = true;
      animation?.destroy();
    };
  }, [state]);

  if (missing) return <WiseOwl className={className} still={state !== "idle"} />;
  // The character fills only the middle of its canvas, so it is drawn half as large again to match the size asked for.
  return <div ref={box} aria-hidden="true" data-bot={state} className={`${className} flex-none scale-150 [&>svg]:block`} />;
}
