// Custom UUS CAPEX Flow navigation icons — one distinct symbol per page.
// Drawn in a single line style (24px grid, rounded joins) per brand doc
// `brand/UUS CAPEX Flow Nav Icons.html`. Icons inherit `currentColor` so the
// sidebar's active/inactive text color applies, matching the prior lucide set.

export interface NavIconProps {
  size?: number
}

function Icon({ size = 24, children }: NavIconProps & { children: React.ReactNode }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {children}
    </svg>
  )
}

export function DashboardIcon(props: NavIconProps) {
  return (
    <Icon {...props}>
      <rect x="3" y="3" width="7" height="9" rx="1.6" />
      <rect x="14" y="3" width="7" height="5" rx="1.6" />
      <rect x="14" y="12" width="7" height="9" rx="1.6" />
      <rect x="3" y="16" width="7" height="5" rx="1.6" />
    </Icon>
  )
}

export function NewRequestIcon(props: NavIconProps) {
  return (
    <Icon {...props}>
      <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
      <path d="M14 3v5h5" />
      <path d="M12 11v6M9 14h6" />
    </Icon>
  )
}

export function MyRequestsIcon(props: NavIconProps) {
  return (
    <Icon {...props}>
      <path d="M4 6l1.6 1.6L8 5" />
      <path d="M4 12l1.6 1.6L8 11" />
      <path d="M4 18l1.6 1.6L8 17" />
      <path d="M11 6h9M11 12h9M11 18h9" />
    </Icon>
  )
}

export function UsersIcon(props: NavIconProps) {
  return (
    <Icon {...props}>
      <circle cx="9" cy="8" r="3" />
      <path d="M3.5 20a5.5 5.5 0 0 1 11 0" />
      <circle cx="17.5" cy="9" r="2.4" />
      <path d="M15.5 20a4.8 4.8 0 0 1 5.5-4.6" />
    </Icon>
  )
}

export function DivisionsIcon(props: NavIconProps) {
  return (
    <Icon {...props}>
      <path d="M4 21V6a1 1 0 0 1 1-1h7a1 1 0 0 1 1 1v15" />
      <path d="M13 10h6a1 1 0 0 1 1 1v10" />
      <path d="M2 21h20" />
      <path d="M7 9h2M7 13h2M7 17h2M16 14h1M16 17h1" />
    </Icon>
  )
}

export function ThresholdsIcon(props: NavIconProps) {
  return (
    <Icon {...props}>
      <path d="M4 7h16M4 17h16" />
      <circle cx="9" cy="7" r="2.6" />
      <circle cx="15" cy="17" r="2.6" />
    </Icon>
  )
}

export function EmailTemplatesIcon(props: NavIconProps) {
  return (
    <Icon {...props}>
      <rect x="3" y="5" width="18" height="14" rx="2" />
      <path d="M3.5 7l8.5 6 8.5-6" />
    </Icon>
  )
}

export function ProfileIcon(props: NavIconProps) {
  return (
    <Icon {...props}>
      <circle cx="12" cy="12" r="9" />
      <circle cx="12" cy="10" r="3" />
      <path d="M6.5 18.5a6 6 0 0 1 11 0" />
    </Icon>
  )
}
