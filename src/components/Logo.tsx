/* eslint-disable @next/next/no-img-element */

/** The godseye lockup from the original console: the red eye photo, the wordmark and the red swoosh. */
export function Logo({ href = "/", eyeSrc }: { href?: string; eyeSrc?: string }) {
  // The single-file preview carries the image inline (window.GE_EYE); the site serves it from /brand.
  const inline = typeof window !== "undefined" ? (window as { GE_EYE?: string }).GE_EYE : undefined;
  eyeSrc = eyeSrc ?? inline ?? "/brand/eye.jpg";
  return (
    <a href={href} className="logo" aria-label="godseye prediction, home">
      <img className="logo-eye" src={eyeSrc} alt="" width={212} height={50} />
      <span className="logo-words">
        <span className="logo-name">
          <span className="w1">Gods</span>
          <span className="w2">eye</span>
        </span>
        <span className="logo-tag">Prediction</span>
        <svg className="logo-swoosh" viewBox="0 0 200 12" aria-hidden="true">
          <path
            d="M2 9 C60 1 140 1 198 7"
            fill="none"
            stroke="#d6192b"
            strokeWidth="2.5"
            strokeLinecap="round"
          />
        </svg>
      </span>
    </a>
  );
}
