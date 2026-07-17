import { api } from './client'

export interface ReportBucket {
  approved_total: string | null
  approved_count: number
  pending_total: string | null
  pending_count: number
}
export interface DivisionBucket extends ReportBucket {
  division: string
}
export interface MonthBucket extends ReportBucket {
  month: number
}
export interface StatusBucket {
  status: string
  count: number
  total: string | null
}
export interface ReportSummary {
  year: number
  years: number[]
  totals: ReportBucket & { request_count: number }
  by_division: DivisionBucket[]
  by_month: MonthBucket[]
  by_status: StatusBucket[]
  cycle_time: { avg_days: number | null; count: number }
}

export function getReportSummary(year?: number): Promise<ReportSummary> {
  return api<ReportSummary>(`/reports/summary${year ? `?year=${year}` : ''}`)
}
