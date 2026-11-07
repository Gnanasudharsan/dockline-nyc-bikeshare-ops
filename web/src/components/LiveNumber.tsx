/**
 * A live number. When the value changes, the new value fades in over 150 ms (keyed
 * CSS animation, disabled by prefers-reduced-motion). Tabular figures avoid jitter.
 */
export function LiveNumber({ value, className = "" }: { value: string; className?: string }) {
  return (
    <span key={value} className={`num live-fade ${className}`}>
      {value}
    </span>
  );
}
