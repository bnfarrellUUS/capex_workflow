/**
 * UUS CAPRI logo mark — brand direction "1d Capital Cycle":
 * a circular flow arrow around a rising chevron (capital moving through the
 * approval cycle). Geometry is taken verbatim from
 * brand/project/UUS CAPEX Flow - Logo.dc.html. `tile` renders it on a navy
 * rounded-square app-icon tile; without it the glyph is transparent for use on
 * dark surfaces. Every consumer draws it on navy, so the mark uses the brand's
 * navy-surface colours (sky arc, white chevron).
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
      viewBox="0 0 100 100"
      fill="none"
      className={className}
      role="img"
      aria-label="UUS CAPRI"
    >
      {tile && <rect width="100" height="100" rx="23" fill="#0B2A4A" />}
      {/* circular flow arrow (cycle) */}
      <path
        d="M74 28 A33 33 0 1 0 82 54"
        stroke="#93BBF5"
        strokeWidth="11"
        strokeLinecap="round"
        fill="none"
      />
      {/* arrowhead at the head of the cycle */}
      <polygon points="63,20 84,20 74,38" fill="#93BBF5" />
      {/* rising chevron */}
      <polyline
        points="38,56 50,44 62,56"
        stroke="#ffffff"
        strokeWidth="11"
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
      />
    </svg>
  )
}
