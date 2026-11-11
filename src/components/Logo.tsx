/** The godseye mark (an eye with a gold iris) and wordmark. Uses the `.logo` styles of whichever section it sits in. */
export function EyeMark({ size = 44 }: { size?: number }) {
  return (
    <svg
      className="logo-mark"
      viewBox="0 0 64 40"
      width={size}
      height={(size * 40) / 64}
      aria-hidden="true"
    >
      <path
        d="M2 20C12 6 23 1 32 1s20 5 30 19C52 34 41 39 32 39S12 34 2 20Z"
        fill="#fff"
      />
      <circle cx="32" cy="20" r="13.5" fill="#ffd400" />
      <circle cx="32" cy="20" r="6.5" fill="#071a5e" />
      <circle cx="35.2" cy="16.8" r="2.1" fill="#fff" />
    </svg>
  );
}

export function Logo({ href = "/" }: { href?: string }) {
  return (
    <a href={href} className="logo" aria-label="godseye predictions, home">
      <EyeMark />
      <span className="logo-words">
        <span className="logo-name">
          Gods<b>eye</b>
        </span>
        <span className="logo-tag">Predictions</span>
      </span>
    </a>
  );
}
