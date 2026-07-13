import type { ReactNode } from 'react'
import {
  DashboardIcon,
  NewRequestIcon,
  MyRequestsIcon,
  UsersIcon,
  DivisionsIcon,
  ThresholdsIcon,
  EmailTemplatesIcon,
  ProfileIcon,
  type NavIconProps,
} from '../NavIcons'

// Brand constants shared with the email frame (navy band, sky subtitle).
const NAVY = '#0B2A4A'
const SKY = '#93BBF5'
// Sky-blue page mark on the navy band, in a soft rounded tile (per brand doc).
const MARK_BLUE = '#5B9BFF'

/** Per-page header mark — each page uses its own nav icon. */
export type PageMark =
  | 'dashboard'
  | 'newRequest'
  | 'requests'
  | 'users'
  | 'divisions'
  | 'thresholds'
  | 'emailTemplates'
  | 'profile'

const MARKS: Record<PageMark, React.ComponentType<NavIconProps>> = {
  dashboard: DashboardIcon,
  newRequest: NewRequestIcon,
  requests: MyRequestsIcon,
  users: UsersIcon,
  divisions: DivisionsIcon,
  thresholds: ThresholdsIcon,
  emailTemplates: EmailTemplatesIcon,
  profile: ProfileIcon,
}

/**
 * Page card matching the notification-email look: rounded card with a navy
 * header band (Capital-Cycle logo + title + sky subtitle), an optional
 * subheader band (e.g. a stepper or filters), a padded body, and an optional
 * footer action bar separated by a hairline — one BrandCard per page.
 */
export function BrandCard({
  title,
  subtitle,
  actions,
  subheader,
  footer,
  mark = 'dashboard',
  bodyClassName = 'px-7 py-6',
  className = '',
  children,
}: {
  title: ReactNode
  subtitle?: ReactNode
  /** Right side of the navy band (e.g. a status badge or primary button). */
  actions?: ReactNode
  /** Band between header and body (caller styles it, e.g. the wizard stepper). */
  subheader?: ReactNode
  /** Footer action bar content; wrapper provides flex + gap + padding. */
  footer?: ReactNode
  /** Which page mark to show — each page uses its own nav icon. */
  mark?: PageMark
  bodyClassName?: string
  className?: string
  children: ReactNode
}) {
  const Mark = MARKS[mark]
  return (
    <div className={`overflow-hidden rounded-2xl border border-border bg-surface shadow-sm ${className}`}>
      <div className="flex items-center gap-3.5 px-7 py-5" style={{ background: NAVY }}>
        <div
          className="flex h-[46px] w-[46px] shrink-0 items-center justify-center rounded-xl"
          style={{ background: 'rgba(91,155,255,0.16)', color: MARK_BLUE }}
        >
          <Mark size={24} />
        </div>
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-xl font-bold text-white">{title}</h1>
          {subtitle && (
            <div className="text-[13px] tracking-wide" style={{ color: SKY }}>{subtitle}</div>
          )}
        </div>
        {actions}
      </div>
      {subheader}
      <div className={bodyClassName}>{children}</div>
      {footer && (
        <div className="flex items-center gap-3 border-t border-border px-7 py-4">{footer}</div>
      )}
    </div>
  )
}
