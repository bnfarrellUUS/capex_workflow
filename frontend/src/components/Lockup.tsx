/**
 * The CAPRI dark lockup — the mark beside the two-tone CAPRI wordmark
 * (brand direction 1d, dark variant; the letterspaced "UUS" from
 * `brand/capri-dark-lockup.png` was dropped 2026-08-18 at Bryan's request).
 *
 * `panel` wraps it in the navy rounded rectangle from that artwork; the sidebar
 * omits it because it is already navy, the login card needs it.
 */
import { Logo } from './Logo'
import { Wordmark } from './Wordmark'

export function Lockup({
  panel = false,
  markSize = 40,
  className = '',
}: {
  panel?: boolean
  markSize?: number
  className?: string
}) {
  const inner = (
    <>
      <Logo size={markSize} />
      <Wordmark tone="dark" className="text-xl font-extrabold tracking-tight leading-none" />
    </>
  )
  if (!panel) {
    return <div className={`flex items-center gap-3.5 ${className}`}>{inner}</div>
  }
  return (
    <div className={`flex items-center gap-3.5 rounded-2xl bg-brand-navy px-5 py-4 ${className}`}>
      {inner}
    </div>
  )
}
