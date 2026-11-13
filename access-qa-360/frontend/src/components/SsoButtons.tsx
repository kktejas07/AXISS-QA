import { useEffect, useState } from "react";
import { getSsoProviders, ssoStartUrl } from "../api/auth";

const names = { google: "Google", microsoft: "Microsoft" } as const;

/** "Continue with Google / Microsoft", shown only for the providers this server has set up. */
export function SsoButtons({ invite }: { invite?: string }) {
  const [on, setOn] = useState<("google" | "microsoft")[]>([]);

  useEffect(() => {
    getSsoProviders()
      .then((r) => setOn((["google", "microsoft"] as const).filter((p) => r.data[p])))
      .catch(() => setOn([]));
  }, []);

  if (on.length === 0) return null;
  return (
    <div className="mb-5 flex flex-col gap-2.5">
      {on.map((p) => (
        <a key={p} href={ssoStartUrl(p, invite)} className="flex h-12 items-center justify-center rounded-[10px] border-[1.5px] border-ink bg-white font-semibold hover:bg-soft">
          Continue with {names[p]}
        </a>
      ))}
      <div className="mt-2 flex items-center gap-3 text-[13.5px] text-body">
        <span className="h-px flex-1 bg-line" />
        or use your email
        <span className="h-px flex-1 bg-line" />
      </div>
    </div>
  );
}
