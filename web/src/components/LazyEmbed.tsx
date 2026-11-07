"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Inserts an iframe only once its box scrolls into view. Browsers' native lazy loading
 * starts far earlier; the Grafana dashboard is heavy, so it waits until it is actually
 * visible. The box keeps its size before and after, so nothing shifts.
 */
export function LazyEmbed({
  src,
  title,
  className,
}: {
  src: string;
  title: string;
  className: string;
}) {
  const box = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const element = box.current;
    if (!element) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setVisible(true);
          observer.disconnect();
        }
      },
      { rootMargin: "0px" },
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  return (
    <div ref={box} className={className}>
      {visible ? (
        <iframe src={src} title={title} className="h-full w-full" />
      ) : (
        <p className="p-4 text-sm text-slate">The live dashboard loads when you scroll to it.</p>
      )}
    </div>
  );
}
