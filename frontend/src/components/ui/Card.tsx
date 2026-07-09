import type { HTMLAttributes, ReactNode } from 'react'

export function Card({ className = '', ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={`rounded-xl border border-border bg-surface shadow-sm ${className}`}
      {...props}
    />
  )
}

export function StatCard({
  label,
  value,
  sub,
  accent = false,
}: {
  label: string
  value: ReactNode
  sub?: ReactNode
  accent?: boolean
}) {
  return (
    <Card className="p-4">
      <div className="text-xs font-semibold uppercase tracking-wide text-muted">{label}</div>
      <div className={`mt-2 text-2xl font-bold ${accent ? 'text-accent' : 'text-fg'}`}>{value}</div>
      {sub != null && <div className="mt-1 text-xs text-muted">{sub}</div>}
    </Card>
  )
}
