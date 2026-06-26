"use client";

/** Re-mounts on every route change, so the fade-in animation plays on navigation. */
export default function Template({ children }: { children: React.ReactNode }) {
  return <div className="page-enter">{children}</div>;
}
