/* eslint-disable @next/next/no-img-element */

/** The godseye lockup: the red eye photo and the wordmark. Uses the `.logo` styles of whichever section it sits in. */
export function Logo({ href = "/" }: { href?: string }) {
  return (
    <a href={href} className="logo" aria-label="godseye predictions, home">
      <img className="logo-eye" src="/brand/eye.jpg" alt="" width={212} height={50} />
      <span className="logo-words">
        <span className="logo-name">
          Gods<b>eye</b>
        </span>
        <span className="logo-tag">Predictions</span>
      </span>
    </a>
  );
}
