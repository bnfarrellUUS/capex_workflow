/* The set of CAPEX requests a person has open at once, kept in localStorage.
 *
 * Nothing here is unsaved -- the wizard persists every save server-side and the
 * detail page is read-only -- so a tab is only ever a pointer plus enough label
 * to render it. Ids alone would mean one request per tab on every page load,
 * which an app-wide strip cannot afford, so each tab carries a label snapshot
 * and the page that loads the request refreshes its own.
 *
 * Ported from SCORE's openBids.ts (bid_template/bid_app). CAPRI adds `mode`
 * because a request has two pages (view and edit) where a bid has one, and
 * drops replaceOpenBid because a request keeps one id for its life.
 */

import { useEffect, useState } from 'react'

export interface OpenRequest {
  id: string
  number: string        // "CX000123"
  title: string         // the request's description, truncated by CSS not here
  /* Which page the person was on, so switching tabs never throws an approver
     into edit mode. */
  mode: 'view' | 'edit'
  /* Which wizard step this request was left on; 0 for a view-only tab. */
  step: number
  /* Bookkeeping only: a monotonic stamp of when this tab was last opened, so the
     cap evicts the least recently seen. On-screen order is insertion order and
     deliberately never changes -- tabs that jump on click cannot be aimed at. */
  seq: number
}

/* Several at once is the use case; eight should never be felt. */
export const MAX_OPEN_REQUESTS = 8

/* Keyed by user: localStorage is per browser, not per account, and two people
   sharing a machine must not inherit each other's tabs. */
export function storageKey(userId: string): string {
  return `capri_open_requests:${userId}`
}

function isOpenRequest(value: unknown): value is OpenRequest {
  const t = value as Partial<OpenRequest> | null
  return (
    typeof t === 'object' &&
    t !== null &&
    typeof t.id === 'string' &&
    typeof t.number === 'string' &&
    typeof t.title === 'string' &&
    (t.mode === 'view' || t.mode === 'edit') &&
    typeof t.step === 'number' &&
    typeof t.seq === 'number'
  )
}

export function readOpenRequests(userId: string): OpenRequest[] {
  try {
    const raw = localStorage.getItem(storageKey(userId))
    if (!raw) return []
    const parsed: unknown = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed.filter(isOpenRequest) : []
  } catch {
    return []
  }
}

/* The strip and the pages both write here, and neither owns the other, so the
   store notifies rather than being lifted into a provider. `useOpenRequests` is
   the only subscriber shape needed -- there is no snapshot identity to get
   wrong, because each listener re-reads for itself. */
const listeners = new Set<() => void>()

function write(userId: string, tabs: OpenRequest[]): OpenRequest[] {
  try {
    localStorage.setItem(storageKey(userId), JSON.stringify(tabs))
  } catch {
    /* storage blocked (private mode / quota): the write is lost and readers see
       the previous value; the strip degrades to read-only rather than throwing */
  }
  listeners.forEach((notify) => notify())
  return tabs
}

export function useOpenRequests(userId: string): OpenRequest[] {
  const [tabs, setTabs] = useState(() => readOpenRequests(userId))

  useEffect(() => {
    const resync = () => setTabs(readOpenRequests(userId))
    listeners.add(resync)
    resync()
    return () => {
      listeners.delete(resync)
    }
  }, [userId])

  return tabs
}

/* Add the request, or refresh the label and mode of the one already there.
   Called whenever a request page loads, which is every entry point -- the list,
   the dashboard, an email deep link, the new-request redirect -- because all of
   them route through the same two URLs. */
export function touchOpenRequest(
  userId: string,
  req: Omit<OpenRequest, 'step' | 'seq'>,
): OpenRequest[] {
  const tabs = readOpenRequests(userId)
  const seq = Math.max(0, ...tabs.map((t) => t.seq)) + 1
  const at = tabs.findIndex((t) => t.id === req.id)

  if (at >= 0) {
    const next = tabs.slice()
    // Spreading the existing tab first keeps its remembered step.
    next[at] = { ...next[at], ...req, seq }
    return write(userId, next)
  }

  let next = [...tabs, { ...req, step: 0, seq }]
  if (next.length > MAX_OPEN_REQUESTS) {
    const oldest = next.reduce((a, b) => (a.seq <= b.seq ? a : b))
    next = next.filter((t) => t !== oldest)
  }
  return write(userId, next)
}

export function setOpenRequestStep(
  userId: string,
  id: string,
  step: number,
): OpenRequest[] {
  const tabs = readOpenRequests(userId)
  if (!tabs.some((t) => t.id === id)) return tabs
  return write(
    userId,
    tabs.map((t) => (t.id === id ? { ...t, step } : t)),
  )
}

export function closeOpenRequest(userId: string, id: string): OpenRequest[] {
  return write(
    userId,
    readOpenRequests(userId).filter((t) => t.id !== id),
  )
}
