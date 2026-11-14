/** What Wise is doing. Each state moves the owl in its own way. */
export type BotState = "idle" | "working" | "typing" | "thinking" | "reading" | "writing" | "designing" | "coding" | "searching" | "listening" | "sleeping" | "done" | "error";

const INK = "#101014", MAIN = "#4338ca", DEEP = "#3730a3", LIGHT = "#a5b4fc", BEAK = "#fbbf24";

// Which parts move for each state. The movement itself is in index.css (the .owl-* rules).
type Mood = { body: "breathe" | "hop" | "shake" | "tilt" | "sway"; look: "ahead" | "scan" | "up" | "down"; eyes: "open" | "closed" | "happy"; wings: "rest" | "flap" | "wave" | "tap"; beak: "shut" | "talk"; extra?: "dots" | "zzz" | "tick" | "bang" };
const moods: Record<BotState, Mood> = {
  idle: { body: "breathe", look: "ahead", eyes: "open", wings: "rest", beak: "shut" },
  listening: { body: "tilt", look: "ahead", eyes: "open", wings: "rest", beak: "shut" },
  thinking: { body: "sway", look: "up", eyes: "open", wings: "rest", beak: "shut", extra: "dots" },
  searching: { body: "breathe", look: "scan", eyes: "open", wings: "rest", beak: "shut" },
  reading: { body: "breathe", look: "scan", eyes: "open", wings: "rest", beak: "shut" },
  typing: { body: "breathe", look: "ahead", eyes: "open", wings: "rest", beak: "talk" },
  writing: { body: "breathe", look: "down", eyes: "open", wings: "tap", beak: "shut" },
  coding: { body: "breathe", look: "down", eyes: "open", wings: "tap", beak: "shut" },
  designing: { body: "sway", look: "down", eyes: "open", wings: "tap", beak: "shut" },
  working: { body: "breathe", look: "down", eyes: "open", wings: "flap", beak: "shut" },
  sleeping: { body: "breathe", look: "ahead", eyes: "closed", wings: "rest", beak: "shut", extra: "zzz" },
  done: { body: "hop", look: "ahead", eyes: "happy", wings: "wave", beak: "shut", extra: "tick" },
  error: { body: "shake", look: "ahead", eyes: "open", wings: "rest", beak: "shut", extra: "bang" },
};

/**
 * Wise, the owl, as a small animated character whose movement shows what it is doing:
 * it blinks and breathes when idle, looks up with three dots when thinking, scans from
 * side to side when searching, moves its beak when answering, flaps when working, and
 * hops with a tick when done. Drawn here, so there are no animation files to install.
 * Decorative: the text next to it says the same thing. Stands still for reduced motion.
 */
export function WiseBot({ state = "idle", className = "h-12 w-12" }: { state?: BotState; className?: string }) {
  const m = moods[state];
  const open = m.eyes === "open";
  return (
    <svg viewBox="0 0 64 64" role="presentation" aria-hidden="true" fill="none" data-bot={state} className={`wise-owl flex-none ${className}`}>
      <g className={`owl-part owl-body-${m.body}`}>
        {/* ear tufts */}
        <g className="owl-part owl-ears">
          <path d="M12 12l12 6-6 8zM52 12l-12 6 6 8z" fill={DEEP} stroke={INK} strokeWidth="2.5" strokeLinejoin="round" />
        </g>
        {/* wings, behind the body so only their tips show at rest */}
        <path className={`owl-part owl-wing-l owl-wings-${m.wings}`} d="M13 30c-6 5-8 13-4 20 4-2 7-7 7-13z" fill={DEEP} stroke={INK} strokeWidth="2.5" strokeLinejoin="round" />
        <path className={`owl-part owl-wing-r owl-wings-${m.wings}`} d="M51 30c6 5 8 13 4 20-4-2-7-7-7-13z" fill={DEEP} stroke={INK} strokeWidth="2.5" strokeLinejoin="round" />
        <path d="M32 12c13 0 21 9 21 22S45 58 32 58 11 47 11 34s8-22 21-22z" fill={MAIN} stroke={INK} strokeWidth="3" />
        <path className="owl-part owl-belly" d="M32 40c8 0 13 5 13 11-3 4-8 7-13 7s-10-3-13-7c0-6 5-11 13-11z" fill={LIGHT} />
        <circle cx="23" cy="30" r="9" fill="#fff" stroke={INK} strokeWidth="2.5" />
        <circle cx="41" cy="30" r="9" fill="#fff" stroke={INK} strokeWidth="2.5" />
        {open ? (
          <g className={`owl-part owl-look-${m.look}`}>
            <g className="owl-part owl-blink">
              <circle cx="24" cy="31" r="4" fill={INK} />
              <circle cx="40" cy="31" r="4" fill={INK} />
            </g>
            <circle cx="25.5" cy="29.5" r="1.3" fill="#fff" />
            <circle cx="41.5" cy="29.5" r="1.3" fill="#fff" />
          </g>
        ) : (
          // closed in sleep (curving down), or squeezed shut in a smile (curving up)
          <path d={m.eyes === "happy" ? "M18.5 32q4.5-6 9 0M36.5 32q4.5-6 9 0" : "M18.5 30q4.5 5 9 0M36.5 30q4.5 5 9 0"} stroke={INK} strokeWidth="2.6" strokeLinecap="round" />
        )}
        <path className={`owl-part owl-beak-${m.beak}`} d="M29 38.5l3 4 3-4z" fill="#f59e0b" stroke={INK} strokeWidth="1.6" strokeLinejoin="round" />
        <path d="M32 35l-4 4.5h8z" fill={BEAK} stroke={INK} strokeWidth="2" strokeLinejoin="round" />
      </g>
      {m.extra === "dots" && (
        <g fill={INK}>
          {[46, 52, 58].map((x, i) => <circle key={x} className="owl-part owl-dot" style={{ animationDelay: `${i * 0.18}s` }} cx={x} cy="8" r="2.4" />)}
        </g>
      )}
      {m.extra === "zzz" && (
        <g stroke={INK} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path className="owl-part owl-zzz" d="M48 10h6l-6 6h6" />
          <path className="owl-part owl-zzz" style={{ animationDelay: "0.9s" }} d="M56 3h4l-4 4h4" />
        </g>
      )}
      {m.extra === "tick" && (
        <g className="owl-part owl-pop">
          <circle cx="52" cy="11" r="8" fill="#10b981" stroke={INK} strokeWidth="2" />
          <path d="M48.2 11.2l2.8 2.8 5-5.4" stroke="#fff" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
        </g>
      )}
      {m.extra === "bang" && (
        <g className="owl-part owl-pop">
          <circle cx="52" cy="11" r="8" fill="#dc2626" stroke={INK} strokeWidth="2" />
          <path d="M52 6.5v5.5" stroke="#fff" strokeWidth="2.6" strokeLinecap="round" />
          <circle cx="52" cy="15.2" r="1.4" fill="#fff" />
        </g>
      )}
    </svg>
  );
}
