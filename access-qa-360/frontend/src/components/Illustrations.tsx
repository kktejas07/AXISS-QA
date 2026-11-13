/**
 * Wiseflow's vector illustrations: flat shapes in the brand indigo with an ink
 * outline and the same hard offset shadow the cards use. Decorative, so each is
 * hidden from screen readers; the text beside it carries the meaning.
 */
type Props = { className?: string };

const INK = "#101014";
const DEEP = "#3730a3";
const MAIN = "#4338ca";
const MID = "#818cf8";
const LIGHT = "#a5b4fc";
const PALE = "#e0e7ff";
const line = { stroke: INK, strokeWidth: 3, strokeLinejoin: "round" as const, strokeLinecap: "round" as const };

function Frame({ className, children }: Props & { children: React.ReactNode }) {
  return (
    <svg viewBox="0 0 240 180" role="presentation" aria-hidden="true" className={className ?? "h-40 w-auto"} fill="none">
      {children}
    </svg>
  );
}

/** A browser window being swept by a radar: nothing scanned yet. */
export function RadarWindow({ className }: Props) {
  return (
    <Frame className={className}>
      <rect x="38" y="34" width="176" height="124" rx="12" fill={DEEP} />
      <rect x="30" y="26" width="176" height="124" rx="12" fill="#fff" {...line} />
      <path d="M30 52h176" {...line} />
      <circle cx="46" cy="39" r="4" fill={MID} />
      <circle cx="60" cy="39" r="4" fill={LIGHT} />
      <circle cx="74" cy="39" r="4" fill={PALE} stroke={INK} strokeWidth="1.5" />
      <circle cx="118" cy="102" r="36" fill={PALE} {...line} />
      <circle cx="118" cy="102" r="22" stroke={MID} strokeWidth="3" />
      <circle cx="118" cy="102" r="8" stroke={MID} strokeWidth="3" />
      <path d="M118 102 144 77A36 36 0 0 1 154 102z" fill={MAIN} {...line} />
      <circle cx="118" cy="102" r="4" fill={INK} />
      <circle cx="98" cy="88" r="5" fill={MAIN} />
      <circle cx="132" cy="120" r="4" fill={MID} />
    </Frame>
  );
}

/** A calendar with a clock: scheduled scans. */
export function CalendarClock({ className }: Props) {
  return (
    <Frame className={className}>
      <rect x="44" y="40" width="140" height="118" rx="12" fill={DEEP} />
      <rect x="36" y="32" width="140" height="118" rx="12" fill="#fff" {...line} />
      <path d="M36 62h140" {...line} />
      <path d="M36 44a12 12 0 0 1 12-12h116a12 12 0 0 1 12 12v18H36z" fill={MAIN} {...line} />
      <path d="M68 22v20M144 22v20" {...line} strokeWidth="5" />
      {[0, 1, 2, 3].map((c) => [0, 1, 2].map((r) => (
        <rect key={`${c}-${r}`} x={52 + c * 29} y={74 + r * 23} width="18" height="14" rx="4" fill={(c + r) % 3 === 0 ? MID : PALE} />
      )))}
      <circle cx="176" cy="132" r="32" fill="#fff" {...line} />
      <circle cx="176" cy="132" r="24" fill={PALE} />
      <path d="M176 116v16l11 8" {...line} strokeWidth="4" />
    </Frame>
  );
}

/** Two report sheets side by side, one line added and one removed: what changed. */
export function CompareSheets({ className }: Props) {
  return (
    <Frame className={className}>
      <rect x="32" y="38" width="84" height="116" rx="10" fill={DEEP} />
      <rect x="24" y="30" width="84" height="116" rx="10" fill="#fff" {...line} />
      <rect x="140" y="38" width="84" height="116" rx="10" fill={DEEP} />
      <rect x="132" y="30" width="84" height="116" rx="10" fill="#fff" {...line} />
      {[52, 72, 112].map((y) => <rect key={y} x="38" y={y} width="56" height="8" rx="4" fill={PALE} />)}
      <rect x="38" y="92" width="56" height="8" rx="4" fill="#fecaca" />
      {[52, 72, 112].map((y) => <rect key={y} x="146" y={y} width="56" height="8" rx="4" fill={PALE} />)}
      <rect x="146" y="92" width="56" height="8" rx="4" fill="#a7f3d0" />
      <circle cx="120" cy="88" r="20" fill={MAIN} {...line} />
      <path d="M110 84h20m-6-6 6 6-6 6M130 94h-20m6-6-6 6 6 6" stroke="#fff" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" transform="translate(0 -1)" />
    </Frame>
  );
}

/** A shield with a checklist: standards. */
export function ShieldList({ className }: Props) {
  return (
    <Frame className={className}>
      <path d="M128 26l62 22v44c0 36-26 60-62 72-36-12-62-36-62-72V48z" fill={DEEP} />
      <path d="M120 18l62 22v44c0 36-26 60-62 72-36-12-62-36-62-72V40z" fill="#fff" {...line} />
      <path d="M120 34l46 16v34c0 27-19 45-46 55z" fill={PALE} />
      {[62, 86, 110].map((y, i) => (
        <g key={y}>
          <circle cx="88" cy={y} r="8" fill={i === 2 ? "#fff" : MAIN} {...line} strokeWidth="2.5" />
          {i < 2 && <path d={`M84 ${y}l3 3 6-6`} stroke="#fff" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />}
          <rect x="104" y={y - 4} width={i === 1 ? 38 : 50} height="8" rx="4" fill={i === 2 ? LIGHT : MID} />
        </g>
      ))}
    </Frame>
  );
}

/** Two plugs meeting: connections to other tools. */
export function Plugs({ className }: Props) {
  return (
    <Frame className={className}>
      <path d="M14 96h44M182 96h44" {...line} strokeWidth="6" />
      <rect x="64" y="70" width="52" height="60" rx="12" fill={DEEP} />
      <rect x="58" y="64" width="52" height="60" rx="12" fill={MAIN} {...line} />
      <path d="M110 82h16M110 106h16" {...line} strokeWidth="6" />
      <rect x="138" y="70" width="52" height="60" rx="12" fill={DEEP} />
      <rect x="132" y="64" width="52" height="60" rx="12" fill="#fff" {...line} />
      <circle cx="146" cy="82" r="5" fill={INK} />
      <circle cx="146" cy="106" r="5" fill={INK} />
      <path d="M120 40l-6 14h12l-6 14" stroke={MID} strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M96 150c8 6 40 6 48 0" stroke={LIGHT} strokeWidth="4" strokeLinecap="round" />
    </Frame>
  );
}

/** A branch merging with a check mark: pull requests. */
export function BranchCheck({ className }: Props) {
  return (
    <Frame className={className}>
      <path d="M70 52v76M70 90c0-22 60-10 60-38" {...line} strokeWidth="6" />
      <circle cx="70" cy="42" r="14" fill="#fff" {...line} />
      <circle cx="70" cy="138" r="14" fill={MID} {...line} />
      <circle cx="130" cy="42" r="14" fill={PALE} {...line} />
      <rect x="126" y="86" width="92" height="66" rx="12" fill={DEEP} />
      <rect x="118" y="78" width="92" height="66" rx="12" fill="#fff" {...line} />
      <circle cx="142" cy="111" r="13" fill={MAIN} {...line} strokeWidth="2.5" />
      <path d="M136 111l4 4 8-8" stroke="#fff" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
      <rect x="162" y="100" width="36" height="8" rx="4" fill={MID} />
      <rect x="162" y="114" width="26" height="8" rx="4" fill={PALE} />
    </Frame>
  );
}

/** A phone showing a six-digit code next to a padlock: two-step sign-in. */
export function PhoneCode({ className }: Props) {
  return (
    <Frame className={className}>
      <rect x="64" y="24" width="78" height="140" rx="14" fill={DEEP} />
      <rect x="56" y="16" width="78" height="140" rx="14" fill="#fff" {...line} />
      <rect x="82" y="24" width="26" height="6" rx="3" fill={INK} />
      <rect x="66" y="52" width="58" height="34" rx="8" fill={PALE} />
      {[0, 1, 2].map((i) => <circle key={i} cx={80 + i * 15} cy="69" r="4.5" fill={MAIN} />)}
      <rect x="66" y="98" width="58" height="8" rx="4" fill={LIGHT} />
      <rect x="66" y="114" width="40" height="8" rx="4" fill={PALE} />
      <rect x="150" y="88" width="64" height="56" rx="12" fill={DEEP} />
      <rect x="144" y="82" width="64" height="56" rx="12" fill={MAIN} {...line} />
      <path d="M160 82V68a16 16 0 0 1 32 0v14" {...line} strokeWidth="5" />
      <circle cx="176" cy="106" r="7" fill="#fff" />
      <path d="M176 110v10" stroke="#fff" strokeWidth="5" strokeLinecap="round" />
    </Frame>
  );
}

/** A gauge with the needle in the fast zone: performance. */
export function SpeedGauge({ className }: Props) {
  return (
    <Frame className={className}>
      <path d="M40 136a84 84 0 0 1 168 0z" fill={DEEP} transform="translate(6 8)" />
      <path d="M40 136a84 84 0 0 1 168 0z" fill="#fff" {...line} />
      <path d="M58 136a66 66 0 0 1 22-49" stroke="#fecaca" strokeWidth="14" />
      <path d="M86 82a66 66 0 0 1 60-10" stroke={LIGHT} strokeWidth="14" />
      <path d="M153 75a66 66 0 0 1 37 61" stroke={MAIN} strokeWidth="14" />
      <path d="M124 136l38-44" {...line} strokeWidth="6" />
      <circle cx="124" cy="136" r="11" fill={INK} />
      <path d="M28 136h192" {...line} strokeWidth="4" />
    </Frame>
  );
}

/** Curly braces around stacked request rows: API testing. */
export function ApiBraces({ className }: Props) {
  return (
    <Frame className={className}>
      <path d="M58 30c-16 0-18 10-18 22v16c0 10-4 18-14 22 10 4 14 12 14 22v16c0 12 2 22 18 22" {...line} strokeWidth="6" stroke={MAIN} />
      <path d="M182 30c16 0 18 10 18 22v16c0 10 4 18 14 22-10 4-14 12-14 22v16c0 12-2 22-18 22" {...line} strokeWidth="6" stroke={MAIN} />
      {[["GET", MAIN, 44], ["POST", DEEP, 78], ["PUT", MID, 112]].map(([verb, colour, y]) => (
        <g key={verb as string}>
          <rect x="74" y={(y as number) + 4} width="100" height="26" rx="8" fill={DEEP} opacity=".25" />
          <rect x="70" y={y as number} width="100" height="26" rx="8" fill="#fff" {...line} strokeWidth="2.5" />
          <rect x="76" y={(y as number) + 6} width="30" height="14" rx="5" fill={colour as string} />
          <rect x="114" y={(y as number) + 9} width="44" height="8" rx="4" fill={PALE} />
        </g>
      ))}
    </Frame>
  );
}

/** A stack of folders with a spark: projects. */
export function FolderStack({ className }: Props) {
  return (
    <Frame className={className}>
      <path d="M46 62h52l12 14h84a10 10 0 0 1 10 10v62a10 10 0 0 1-10 10H46a10 10 0 0 1-10-10V72a10 10 0 0 1 10-10z" fill={DEEP} transform="translate(8 8)" />
      <path d="M46 46h52l12 14h84a10 10 0 0 1 10 10v8H36V56a10 10 0 0 1 10-10z" fill={LIGHT} {...line} />
      <path d="M36 78h168v70a10 10 0 0 1-10 10H46a10 10 0 0 1-10-10z" fill="#fff" {...line} />
      <rect x="54" y="98" width="72" height="9" rx="4.5" fill={MID} />
      <rect x="54" y="116" width="104" height="9" rx="4.5" fill={PALE} />
      <rect x="54" y="134" width="56" height="9" rx="4.5" fill={PALE} />
      <path d="M178 20l5 13 13 5-13 5-5 13-5-13-13-5 13-5z" fill={MAIN} {...line} strokeWidth="2.5" />
    </Frame>
  );
}

/** Wise, the assistant: a round-eyed owl in the brand indigo. Its eyes blink; pass `still` to stop that. */
export function WiseOwl({ className, still }: Props & { still?: boolean }) {
  const blink = still ? undefined : "wf-blink";
  return (
    <svg viewBox="0 0 64 64" role="presentation" aria-hidden="true" className={className ?? "h-12 w-12"} fill="none">
      <path d="M14 14l8 8M50 14l-8 8" stroke={INK} strokeWidth="3" strokeLinecap="round" />
      <path d="M12 12l12 6-6 8zM52 12l-12 6 6 8z" fill={DEEP} stroke={INK} strokeWidth="2.5" strokeLinejoin="round" />
      <path d="M32 12c13 0 21 9 21 22S45 58 32 58 11 47 11 34s8-22 21-22z" fill={MAIN} stroke={INK} strokeWidth="3" />
      <path d="M32 40c8 0 13 5 13 11-3 4-8 7-13 7s-10-3-13-7c0-6 5-11 13-11z" fill={LIGHT} />
      <circle cx="23" cy="30" r="9" fill="#fff" stroke={INK} strokeWidth="2.5" />
      <circle cx="41" cy="30" r="9" fill="#fff" stroke={INK} strokeWidth="2.5" />
      <circle cx="24" cy="31" r="4" fill={INK} className={blink} />
      <circle cx="40" cy="31" r="4" fill={INK} className={blink} />
      <circle cx="25.5" cy="29.5" r="1.3" fill="#fff" />
      <circle cx="41.5" cy="29.5" r="1.3" fill="#fff" />
      <path d="M32 35l-4 5h8z" fill="#fbbf24" stroke={INK} strokeWidth="2" strokeLinejoin="round" />
    </svg>
  );
}

/** Wise beside two chat bubbles: ask a question. */
export function WiseChat({ className }: Props) {
  return (
    <Frame className={className}>
      <rect x="98" y="30" width="118" height="46" rx="14" fill={DEEP} transform="translate(6 6)" />
      <rect x="98" y="30" width="118" height="46" rx="14" fill="#fff" {...line} />
      <path d="M112 76l-10 14 22-14z" fill="#fff" {...line} />
      <rect x="114" y="44" width="70" height="8" rx="4" fill={MID} />
      <rect x="114" y="58" width="46" height="8" rx="4" fill={PALE} />
      <rect x="120" y="104" width="96" height="40" rx="14" fill={MAIN} {...line} />
      <rect x="136" y="116" width="52" height="8" rx="4" fill="#fff" />
      <rect x="136" y="128" width="30" height="6" rx="3" fill={LIGHT} />
      <g transform="translate(14 62) scale(1.5)">
        <path d="M12 12l12 6-6 8zM52 12l-12 6 6 8z" fill={DEEP} stroke={INK} strokeWidth="2" strokeLinejoin="round" />
        <path d="M32 12c13 0 21 9 21 22S45 58 32 58 11 47 11 34s8-22 21-22z" fill={MAIN} stroke={INK} strokeWidth="2.2" />
        <path d="M32 40c8 0 13 5 13 11-3 4-8 7-13 7s-10-3-13-7c0-6 5-11 13-11z" fill={LIGHT} />
        <circle cx="23" cy="30" r="9" fill="#fff" stroke={INK} strokeWidth="2" />
        <circle cx="41" cy="30" r="9" fill="#fff" stroke={INK} strokeWidth="2" />
        <circle cx="24" cy="31" r="4" fill={INK} />
        <circle cx="40" cy="31" r="4" fill={INK} />
        <path d="M32 35l-4 5h8z" fill="#fbbf24" stroke={INK} strokeWidth="1.6" strokeLinejoin="round" />
      </g>
    </Frame>
  );
}

/** Pages joined by arrows: the map of an app's flows. */
export function FlowMap({ className }: Props) {
  return (
    <Frame className={className}>
      <path d="M78 90h30M146 62h-20v28M146 122h-20V90M190 62h10v60h-10" {...line} strokeWidth="4" stroke={MID} />
      {[[22, 68, MAIN], [146, 40, "#fff"], [146, 100, "#fff"]].map(([x, y, fill], i) => (
        <g key={i}>
          <rect x={(x as number) + 5} y={(y as number) + 5} width="56" height="44" rx="8" fill={DEEP} />
          <rect x={x as number} y={y as number} width="56" height="44" rx="8" fill={fill as string} {...line} />
          <rect x={(x as number) + 9} y={(y as number) + 11} width="30" height="6" rx="3" fill={i ? MID : "#fff"} />
          <rect x={(x as number) + 9} y={(y as number) + 24} width="38" height="6" rx="3" fill={i ? PALE : LIGHT} />
        </g>
      ))}
      <circle cx="108" cy="90" r="9" fill="#fff" {...line} />
      <path d="M104 90h8m-3-3 3 3-3 3" stroke={INK} strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
    </Frame>
  );
}

/** A row of books with a bookmark: the library of ready-made packs. */
export function BookShelf({ className }: Props) {
  return (
    <Frame className={className}>
      <rect x="34" y="146" width="180" height="12" rx="4" fill={DEEP} />
      <rect x="28" y="140" width="180" height="12" rx="4" fill="#fff" {...line} />
      {[[40, 60, 26, MAIN], [70, 44, 30, "#fff"], [104, 70, 24, MID], [132, 52, 28, PALE]].map(([x, y, w, fill], i) => (
        <g key={i}>
          <rect x={x as number} y={y as number} width={w as number} height={140 - (y as number)} rx="4" fill={fill as string} {...line} />
          <rect x={(x as number) + 6} y={(y as number) + 14} width={(w as number) - 12} height="6" rx="3" fill={i % 2 ? MID : "#fff"} />
        </g>
      ))}
      <rect x="160" y="62" width="30" height="80" rx="4" fill={LIGHT} {...line} transform="rotate(14 175 140)" />
      <path d="M80 30v26l8-7 8 7V30z" fill="#fbbf24" {...line} strokeWidth="2.5" />
    </Frame>
  );
}

/** A clipboard with ticks and a pencil: a pack of test cases. */
export function ClipboardTicks({ className }: Props) {
  return (
    <Frame className={className}>
      <rect x="62" y="34" width="110" height="130" rx="12" fill={DEEP} />
      <rect x="54" y="26" width="110" height="130" rx="12" fill="#fff" {...line} />
      <rect x="86" y="16" width="46" height="22" rx="8" fill={MAIN} {...line} />
      {[60, 86, 112].map((y, i) => (
        <g key={y}>
          <rect x="70" y={y} width="18" height="18" rx="5" fill={i < 2 ? MAIN : "#fff"} {...line} strokeWidth="2.5" />
          {i < 2 && <path d={`M74 ${y + 9}l4 4 7-8`} stroke="#fff" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />}
          <rect x="98" y={y + 5} width={[50, 38, 44][i]} height="8" rx="4" fill={i < 2 ? MID : PALE} />
        </g>
      ))}
      <path d="M176 70l22 22-52 52-26 6 6-26z" fill="#fbbf24" {...line} />
      <path d="M168 78l22 22" {...line} />
    </Frame>
  );
}

/** A rocket leaving a launch pad: a preset that starts a scan in one click. */
export function Rocket({ className }: Props) {
  return (
    <Frame className={className}>
      <path d="M120 22c26 18 34 52 26 92h-52c-8-40 0-74 26-92z" fill={DEEP} transform="translate(6 6)" />
      <path d="M120 22c26 18 34 52 26 92h-52c-8-40 0-74 26-92z" fill="#fff" {...line} />
      <circle cx="120" cy="66" r="13" fill={MID} {...line} />
      <path d="M94 92l-22 26h24zM146 92l22 26h-24z" fill={MAIN} {...line} />
      <path d="M106 114h28l-6 14h-16z" fill={INK} />
      <path d="M112 132c0 12 8 16 8 26 0-10 8-14 8-26z" fill="#fbbf24" {...line} strokeWidth="2.5" />
      <path d="M40 158h160" {...line} strokeWidth="4" />
      <circle cx="60" cy="48" r="4" fill={LIGHT} />
      <circle cx="184" cy="36" r="5" fill={MID} />
      <circle cx="196" cy="84" r="3" fill={LIGHT} />
    </Frame>
  );
}

/** A small panel that pairs an illustration with a heading, a sentence and an action: used for empty screens. */
export function EmptyPanel({ art, title, children, action }: { art: React.ReactNode; title: string; children: React.ReactNode; action?: React.ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-4 rounded-2xl border border-gray-300 bg-white px-6 py-12 text-center">
      {art}
      <h2 className="text-xl font-bold">{title}</h2>
      <p className="max-w-[52ch] text-body">{children}</p>
      {action}
    </div>
  );
}
