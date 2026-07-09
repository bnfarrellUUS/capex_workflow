import type { ReactNode } from 'react'

type Tone = 'slate' | 'blue' | 'amber' | 'green' | 'red'

const TONES: Record<Tone, string> = {
  slate: 'bg-slate-100 text-slate-600 dark:bg-slate-500/15 dark:text-slate-300',
  blue: 'bg-blue-100 text-blue-700 dark:bg-blue-500/15 dark:text-blue-300',
  amber: 'bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300',
  green: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300',
  red: 'bg-red-100 text-red-700 dark:bg-red-500/15 dark:text-red-300',
}

export function Badge({ tone = 'slate', children }: { tone?: Tone; children: ReactNode }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${TONES[tone]}`}
    >
      {children}
    </span>
  )
}

const STATUS_TONE: Record<string, Tone> = {
  DRAFT: 'slate',
  PENDING_L1: 'amber',
  PENDING_L2: 'amber',
  PENDING_L3: 'amber',
  APPROVED: 'green',
  REJECTED: 'red',
}

const STATUS_LABEL: Record<string, string> = {
  DRAFT: 'Draft',
  PENDING_L1: 'Pending L1',
  PENDING_L2: 'Pending L2',
  PENDING_L3: 'Pending L3',
  APPROVED: 'Approved',
  REJECTED: 'Rejected',
}

export function StatusBadge({ status }: { status: string }) {
  return <Badge tone={STATUS_TONE[status] ?? 'blue'}>{STATUS_LABEL[status] ?? status}</Badge>
}
