import { useState } from 'react'
import { Navigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { getReportSummary, type ReportBucket } from '../api/reports'
import { useMe } from '../auth/useMe'
import { BrandCard } from '../components/ui/BrandCard'
import { StatCard } from '../components/ui/Card'
import { Select } from '../components/ui/Select'

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

function money(v: string | null | undefined): string {
  return `$${Number(v ?? 0).toLocaleString()}`
}

const THEAD =
  'border-b border-border bg-brand-sky/25 text-left text-xs uppercase tracking-wide ' +
  'text-brand-navy dark:bg-brand-sky/10 dark:text-brand-sky'

function Bar({ value, max }: { value: number; max: number }) {
  const pct = max > 0 && value > 0 ? Math.max(2, Math.round((value / max) * 100)) : 0
  return (
    <div className="h-2 w-full min-w-24 rounded bg-surface-2">
      <div className="h-2 rounded bg-accent" style={{ width: `${pct}%` }} />
    </div>
  )
}

function BucketTable({ title, rows }: {
  title: string
  rows: (ReportBucket & { label: string })[]
}) {
  const max = Math.max(...rows.map((r) => Number(r.approved_total ?? 0)), 0)
  return (
    <section className="mt-8 first:mt-0">
      <h2 className="mb-2 text-sm font-semibold text-fg">{title}</h2>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className={`${THEAD} [&>th]:py-2 [&>th]:pr-4 [&>th:first-child]:pl-2`}>
              <th className="font-semibold">{title === 'Spend by month' ? 'Month' : 'Division'}</th>
              <th className="text-right font-semibold">Approved</th>
              <th className="w-1/3 font-semibold"><span className="sr-only">Share</span></th>
              <th className="text-right font-semibold">Pending</th>
              <th className="pr-2 text-right font-semibold">Requests</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.label} className="border-b border-border last:border-0">
                <td className="py-2 pl-2 pr-4 text-fg">{r.label}</td>
                <td className="py-2 pr-4 text-right font-medium text-fg">{money(r.approved_total)}</td>
                <td className="py-2 pr-4"><Bar value={Number(r.approved_total ?? 0)} max={max} /></td>
                <td className="py-2 pr-4 text-right text-muted">{money(r.pending_total)}</td>
                <td className="py-2 pr-2 text-right text-muted">{r.approved_count + r.pending_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

export default function ReportsPage() {
  const { data: me } = useMe()
  const [year, setYear] = useState<number | undefined>(undefined)
  const canView = (me?.roles ?? []).some((r) => r === 'FINANCE' || r === 'ADMIN')
  const { data } = useQuery({
    queryKey: ['report-summary', year],
    queryFn: () => getReportSummary(year),
    enabled: !!me && canView,
  })

  if (me && !canView) return <Navigate to="/" replace />

  const yearOptions = data?.years ?? (year ? [year] : [])
  const statusMax = Math.max(...(data?.by_status ?? []).map((s) => Number(s.total ?? 0)), 0)

  const subheader = (
    <div className="flex items-center gap-3 border-b border-border bg-surface-2 px-7 py-3">
      <label htmlFor="report-year" className="text-sm font-medium text-muted">Year</label>
      <div className="w-32">
        <Select
          id="report-year"
          aria-label="Year"
          value={String(data?.year ?? year ?? '')}
          onChange={(e) => setYear(Number(e.target.value))}
        >
          {yearOptions.map((y) => (
            <option key={y} value={y}>{y}</option>
          ))}
        </Select>
      </div>
    </div>
  )

  return (
    <BrandCard
      title="Reports"
      subtitle="Spend and cycle-time summaries"
      mark="reports"
      subheader={subheader}
    >
      {!data ? (
        <p className="text-sm text-muted">Loading…</p>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <StatCard label="Approved Spend" value={money(data.totals.approved_total)} accent
              sub={`${data.totals.approved_count} requests`} />
            <StatCard label="Pending Pipeline" value={money(data.totals.pending_total)}
              sub={`${data.totals.pending_count} requests`} />
            <StatCard label="Requests" value={data.totals.request_count}
              sub={`in ${data.year}`} />
            <StatCard label="Avg Days to Approve"
              value={data.cycle_time.avg_days ?? '—'}
              sub={`${data.cycle_time.count} approved`} />
          </div>

          <div className="mt-8">
            <BucketTable
              title="Spend by division"
              rows={data.by_division.map((d) => ({ ...d, label: d.division }))}
            />
            <BucketTable
              title="Spend by month"
              rows={data.by_month.map((m) => ({ ...m, label: MONTHS[m.month - 1] }))}
            />
            <section className="mt-8">
              <h2 className="mb-2 text-sm font-semibold text-fg">By status</h2>
              <div className="overflow-x-auto">
                <table className="w-full border-collapse text-sm">
                  <thead>
                    <tr className={`${THEAD} [&>th]:py-2 [&>th]:pr-4 [&>th:first-child]:pl-2`}>
                      <th className="font-semibold">Status</th>
                      <th className="text-right font-semibold">Requests</th>
                      <th className="text-right font-semibold">Total</th>
                      <th className="w-1/3 pr-2 font-semibold"><span className="sr-only">Share</span></th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.by_status.map((s) => (
                      <tr key={s.status} className="border-b border-border last:border-0">
                        <td className="py-2 pl-2 pr-4 text-fg">{s.status}</td>
                        <td className="py-2 pr-4 text-right text-fg">{s.count}</td>
                        <td className="py-2 pr-4 text-right font-medium text-fg">{money(s.total)}</td>
                        <td className="py-2 pr-2"><Bar value={Number(s.total ?? 0)} max={statusMax} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          </div>
        </>
      )}
    </BrandCard>
  )
}
