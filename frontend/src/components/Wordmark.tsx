/**
 * CAPRI wordmark — "CAP" in the base colour, "RI" in the accent, per brand
 * direction 1d (brand/project/UUS CAPEX Flow - Logo.dc.html).
 *
 * `tone` picks the surface: `dark` for navy (sidebar, email header band),
 * `light` for white cards (login). The split lives here so the three
 * consumers can't drift apart.
 */
export function Wordmark({ tone, className = '' }: {
  tone: 'dark' | 'light'
  className?: string
}) {
  const cap = tone === 'dark' ? 'text-white' : 'text-brand-navy'
  const ri = tone === 'dark' ? 'text-brand-sky' : 'text-brand-blue'
  return (
    <span className={className}>
      <span className={cap}>CAP</span>
      <span className={ri}>RI</span>
    </span>
  )
}
