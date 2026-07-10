/**
 * The four UUS CAPEX Flow logo marks from the brand assets
 * (brand/UUS CAPEX Flow - Logo.dc.html), drawn for dark/navy surfaces:
 *  - cycle  (1d "Capital Cycle")  — primary mark, same as components/Logo.tsx
 *  - ascent (twin rising chevrons) — used for the Requests section
 *  - check  (double checkmark)     — used for the Admin section
 *  - uptime (U with rising chevron) — used for the Account section
 */
export type BrandMarkVariant = 'cycle' | 'ascent' | 'check' | 'uptime'

const BLUE = '#5B9BFF'
const SKY = '#93BBF5'

export function BrandMark({
  variant = 'cycle',
  size = 40,
  className = '',
}: {
  variant?: BrandMarkVariant
  size?: number
  className?: string
}) {
  const common = {
    width: size,
    height: size,
    fill: 'none' as const,
    className,
    role: 'img',
    'aria-label': 'UUS CAPEX Flow',
  }
  if (variant === 'ascent') {
    return (
      <svg {...common} viewBox="0 0 100 100">
        <polyline points="20,62 50,38 80,62" stroke={BLUE} strokeWidth="12"
          strokeLinecap="round" strokeLinejoin="round" />
        <polyline points="20,46 50,22 80,46" stroke="#ffffff" strokeWidth="12"
          strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    )
  }
  if (variant === 'check') {
    return (
      <svg {...common} viewBox="0 0 100 100">
        <polyline points="18,52 40,72 80,22" stroke={BLUE} strokeWidth="12"
          strokeLinecap="round" strokeLinejoin="round" />
        <polyline points="30,52 52,72 92,22" stroke="#ffffff" strokeWidth="12"
          strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    )
  }
  if (variant === 'uptime') {
    return (
      <svg {...common} viewBox="0 0 100 100">
        <path d="M30 24 V56 Q30 74 50 74 Q70 74 70 56 V24" stroke="#ffffff"
          strokeWidth="13" strokeLinecap="round" />
        <polyline points="40,54 50,44 60,54" stroke={BLUE} strokeWidth="10"
          strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    )
  }
  // cycle — primary mark (same geometry as components/Logo.tsx)
  return (
    <svg {...common} viewBox="0 0 48 48">
      <path d="M36.6 15.9 A15 15 0 1 1 24 9" stroke="#2563EB" strokeWidth="4"
        strokeLinecap="round" />
      <path d="M24 9 L18.5 6.5 L19.8 13 Z" fill="#2563EB" />
      <path d="M28 15 L18 24 L28 33" stroke={SKY} strokeWidth="4"
        strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}
