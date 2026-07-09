/**
 * UUS CAPEX Flow logo mark — direction "1d Capital Cycle":
 * a circular flow arrow around a rising chevron (capital moving through the
 * approval cycle). `tile` renders it on a navy rounded-square app-icon tile;
 * without it the glyph is transparent for use on dark surfaces.
 */
export function Logo({
  size = 40,
  tile = false,
  className = '',
}: {
  size?: number
  tile?: boolean
  className?: string
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 48 48"
      fill="none"
      className={className}
      role="img"
      aria-label="UUS CAPEX Flow"
    >
      {tile && <rect width="48" height="48" rx="12" fill="#0B2A4A" />}
      {/* circular flow arrow (cycle) */}
      <path
        d="M36.6 15.9 A15 15 0 1 1 24 9"
        stroke="#2563EB"
        strokeWidth="4"
        strokeLinecap="round"
        fill="none"
      />
      {/* arrowhead at the head of the cycle */}
      <path d="M24 9 L18.5 6.5 L19.8 13 Z" fill="#2563EB" />
      {/* rising chevron */}
      <path
        d="M28 15 L18 24 L28 33"
        stroke="#93BBF5"
        strokeWidth="4"
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
      />
    </svg>
  )
}
