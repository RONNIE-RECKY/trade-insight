"use client";

import { useState } from "react";

/**
 * Shows a partner logo image on a clean white chip (so logos with their own
 * black/white backgrounds still look uniform and professional). Falls back to
 * the partner name if the image file isn't present yet.
 */
export function PartnerLogo({ src, name }: { src: string; name: string }) {
  const [failed, setFailed] = useState(false);

  if (failed) {
    return <span className="text-sm font-semibold tracking-wide text-neutral-500">{name}</span>;
  }

  return (
    <span className="inline-flex h-9 items-center rounded-md bg-white px-3 shadow-sm ring-1 ring-black/5">
      {/* plain img (not next/image) so it works from /public without config */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={src} alt={name} className="h-5 w-auto object-contain" onError={() => setFailed(true)} />
    </span>
  );
}
