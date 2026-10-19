// Brand mark drawn inline (same geometry as public/brand/symbol.svg) so the wordmark next to it
// can use the page's Manrope; an <img> SVG would fall back to a system font.
export function Mark({ size = 32, className = '' }) {
  return (
    <svg viewBox="0 0 48 48" width={size} height={size} className={`brand-mark ${className}`} aria-hidden="true" focusable="false">
      <g fill="none" strokeLinecap="round" strokeWidth="6.5">
        <path d="M39.76 21.22A16 16 0 0 1 19.86 39.45" stroke="var(--brand-cobalt)" />
        <path d="M10.14 32A16 16 0 0 1 24 8" stroke="var(--brand-cobalt)" />
        <path d="M19 29L29 19" stroke="var(--brand-chartreuse)" />
      </g>
      <circle cx="34.28" cy="11.74" r="3.6" fill="var(--brand-chartreuse)" />
    </svg>
  );
}

export function Wordmark({ tagline = false }) {
  return (
    <span className="wordmark">
      <b>Oportuniza<span>Vaga</span></b>
      {tagline && <small>Sinal que vira movimento</small>}
    </span>
  );
}
