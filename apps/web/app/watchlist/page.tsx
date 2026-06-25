"use client";

import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import Link from "next/link";
import { addWatchlistItem, getWatchlist, listSymbols, removeWatchlistItem } from "@/lib/api";

export default function WatchlistPage() {
  const { data: session, status } = useSession();
  const userId = session?.user ? Number((session.user as { id?: string }).id) : null;

  const [allSymbols, setAllSymbols] = useState<string[]>([]);
  const [watched, setWatched] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listSymbols().then((res) => setAllSymbols(res.symbols));
  }, []);

  useEffect(() => {
    if (!userId) return;
    getWatchlist(userId)
      .then((res) => setWatched(res.symbols))
      .catch((e) => setError(String(e)));
  }, [userId]);

  async function toggle(symbol: string) {
    if (!userId) return;
    try {
      if (watched.includes(symbol)) {
        await removeWatchlistItem(userId, symbol);
        setWatched((w) => w.filter((s) => s !== symbol));
      } else {
        await addWatchlistItem(userId, symbol);
        setWatched((w) => [...w, symbol]);
      }
    } catch (e) {
      setError(String(e));
    }
  }

  if (status === "loading") return <p className="text-sm text-neutral-500">Loading…</p>;

  if (!session?.user) {
    return (
      <p className="text-sm text-neutral-400">
        <Link href="/login" className="text-cyan-400 underline underline-offset-2">
          Log in
        </Link>{" "}
        to manage your watchlist.
      </p>
    );
  }

  return (
    <div className="space-y-4">
      <h1 className="text-lg font-semibold text-neutral-100">Watchlist</h1>
      {error && <p className="text-rose-400 text-sm">{error}</p>}
      <ul className="space-y-2">
        {allSymbols.map((s) => (
          <li
            key={s}
            className="flex items-center justify-between bg-neutral-900/60 border border-neutral-800 rounded-lg px-4 py-2.5"
          >
            <span className="text-sm font-mono text-neutral-200">{s}</span>
            <button
              onClick={() => toggle(s)}
              className={`text-xs font-medium px-3 py-1 rounded-md ${
                watched.includes(s)
                  ? "bg-rose-500/10 text-rose-400 border border-rose-500/20"
                  : "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
              }`}
            >
              {watched.includes(s) ? "Remove" : "Add"}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
