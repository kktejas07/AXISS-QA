import { useEffect, useState } from "react";
import { getMe } from "../api/auth";
import type { Me, Permission } from "../types";

// One /auth/me request per sign-in, shared by every component that needs the user.
let cached: Me | null = null;
let pending: Promise<Me> | null = null;

export function fetchMe(): Promise<Me> {
  if (cached) return Promise.resolve(cached);
  if (!pending) {
    pending = getMe()
      .then((r) => {
        cached = r.data;
        return r.data;
      })
      .finally(() => {
        pending = null;
      });
  }
  return pending;
}

/** Forget the signed-in user. Call on sign-out and before a new sign-in. */
export function clearMe() {
  cached = null;
  pending = null;
}

/** The signed-in user, or null while it is loading. */
export function useMe(): Me | null {
  const [me, setMe] = useState<Me | null>(cached);
  useEffect(() => {
    let alive = true;
    fetchMe()
      .then((u) => alive && setMe(u))
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, []);
  return me;
}

/** Whether the signed-in user's role allows an action. Undefined while the user is loading. */
export function useCan(permission: Permission): boolean | undefined {
  const me = useMe();
  return me ? me.permissions.includes(permission) : undefined;
}
