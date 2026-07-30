/**
 * The UUS CAPRI dark lockup — the mark beside a small letterspaced "UUS" over
 * the two-tone CAPRI wordmark, as delivered in `brand/capri-dark-lockup.png`
 * (brand direction 1d, dark variant).
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
      <div className="leading-none">
        <div className="mb-1.5 text-[10px] font-semibold tracking-[0.24em] text-brand-accent">
          UUS
        </div>
        <Wordmark tone="dark" className="text-xl font-extrabold tracking-tight" />
      </div>
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
