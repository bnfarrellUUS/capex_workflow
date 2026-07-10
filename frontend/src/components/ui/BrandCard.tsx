import type { ReactNode } from 'react'
import { BrandMark, type BrandMarkVariant } from '../BrandMark'

// Brand constants shared with the email frame (navy band, sky subtitle).
const NAVY = '#0B2A4A'
const SKY = '#93BBF5'

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
  mark = 'cycle',
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
  /** Which brand logo mark to show — one per app section. */
  mark?: BrandMarkVariant
  bodyClassName?: string
  className?: string
  children: ReactNode
}) {
  return (
    <div className={`overflow-hidden rounded-2xl border border-border bg-surface shadow-sm ${className}`}>
      <div className="flex items-center gap-3.5 px-7 py-5" style={{ background: NAVY }}>
        <BrandMark variant={mark} size={40} />
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
