import type { ReactNode } from 'react'
import {
  DraftIcon,
  PendingIcon,
  ApprovedIcon,
  RejectedIcon,
} from '../ActionIcons'

type Tone = 'slate' | 'blue' | 'amber' | 'green' | 'red'

const TONES: Record<Tone, string> = {
  slate: 'bg-slate-100 text-slate-600 dark:bg-slate-500/15 dark:text-slate-300',
  blue: 'bg-blue-100 text-blue-700 dark:bg-blue-500/15 dark:text-blue-300',
  amber: 'bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300',
  green: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300',
  red: 'bg-red-100 text-red-700 dark:bg-red-500/15 dark:text-red-300',
}

export function Badge({ tone = 'slate', icon, children }: { tone?: Tone; icon?: ReactNode; children: ReactNode }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold ${TONES[tone]}`}
    >
      {icon}
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

const STATUS_ICON: Record<string, ReactNode> = {
  DRAFT: <DraftIcon size={13} strokeWidth={2} />,
  PENDING_L1: <PendingIcon size={13} strokeWidth={2} />,
  PENDING_L2: <PendingIcon size={13} strokeWidth={2} />,
  PENDING_L3: <PendingIcon size={13} strokeWidth={2} />,
  APPROVED: <ApprovedIcon size={13} strokeWidth={2.4} />,
  REJECTED: <RejectedIcon size={13} strokeWidth={2.4} />,
}

export function StatusBadge({ status }: { status: string }) {
  return (
    <Badge tone={STATUS_TONE[status] ?? 'blue'} icon={STATUS_ICON[status]}>
      {STATUS_LABEL[status] ?? status}
    </Badge>
  )
}
