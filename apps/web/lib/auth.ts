"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import { getMe, type UserProfile } from "@/lib/api";

export function useRequireAuth() {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    async function checkAuth() {
      try {
        const me = await getMe();
        if (active) {
          setUser(me);
          setLoading(false);
        }
      } catch (err) {
        if (active) {
          setLoading(false);
          if (pathname !== "/login" && pathname !== "/register") {
            router.push("/login");
          }
        }
      }
    }
    checkAuth();
    return () => {
      active = false;
    };
  }, [router, pathname]);

  return { user, loading };
}

export async function getSession(): Promise<{ userId: string; user?: UserProfile } | null> {
  try {
    const me = await getMe();
    return { userId: me.id, user: me };
  } catch {
    return null;
  }
}
