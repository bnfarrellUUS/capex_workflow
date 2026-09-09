import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import { listPings, type PingSummary } from '../api/pings'
import { Button } from './ui/Button'
import { SendIcon } from './ActionIcons'
import { PingCard, statusOf, type Box } from './PingCard'
import { PingDetail } from './PingDetail'
import { PingModal, type PingInit } from './PingModal'

export type { Box } from './PingCard'
export type Filter = 'open' | 'unread' | 'read' | 'done'

export const FILTERS: [Filter, string][] = [
  ['open', 'Open'], ['unread', 'Unread'], ['read', 'Read'], ['done', 'Done'],
]

export function matches(ping: PingSummary, filter: Filter): boolean {
  return filter === 'open' ? statusOf(ping) !== 'done' : statusOf(ping) === filter
}

/** Search covers sender, recipients, the request number, the note and every
 *  REPLY's text (the server's search_blob). */
export function haystack(ping: PingSummary): string {
  return [ping.note, ping.sender.name, ...ping.recipients.map((r) => r.name),
          ping.request?.number, ping.search_blob]
    .filter(Boolean).join(' ').toLowerCase()
}

/** Filter chips shared by the panel and the Messages page. */
export function FilterChips({ pings, filter, onChange }: {
  pings: PingSummary[]; filter: Filter; onChange: (f: Filter) => void
}) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {FILTERS.map(([key, label]) => {
        const count = pings.filter((p) => matches(p, key)).length
        const on = filter === key
        return (
          <button key={key} type="button" onClick={() => onChange(key)}
            className={`rounded-full border px-2.5 py-0.5 text-xs ${
              on ? 'border-accent bg-accent/10 font-semibold text-accent' : 'border-border text-muted'}`}>
            {label}
            {count > 0 && <span className="ml-1.5 opacity-75 tabular-nums">{count}</span>}
          </button>
        )
      })}
    </div>
  )
}

/** The bell's quick view: 440px, right-anchored, light surface (spec section 8.4). */
export function PingPanel({ onClose }: { onClose: () => void }) {
  const [box, setBox] = useState<Box>('inbox')
  const [filter, setFilter] = useState<Filter>('open')
  const [search, setSearch] = useState('')
  const [openId, setOpenId] = useState<string | null>(null)
  const [composing, setComposing] = useState<PingInit | null>(null)

  const { data: pings = [] } = useQuery({ queryKey: ['pings', 'list', box], queryFn: () => listPings(box) })

  const term = search.trim().toLowerCase()
  const searched = term ? pings.filter((p) => haystack(p).includes(term)) : pings
  const shown = searched.filter((p) => matches(p, filter))

  return (
    <div className="fixed inset-0 z-[1100] bg-black/50"
      onMouseDown={(e) => { if (e.target === e.currentTarget) onClose() }}>
      <aside role="dialog" aria-modal="true" aria-label="Messages"
        className="absolute inset-y-0 right-0 flex w-[440px] max-w-full flex-col border-l border-border bg-surface text-fg">
        <header className="flex items-center gap-2 border-b border-border px-4 py-3">
          <span className="flex-1 text-sm font-bold">🔔 Messages</span>
          <Button size="sm" onClick={() => setComposing({})}><SendIcon size={14} />New Ping</Button>
          <button type="button" onClick={onClose} aria-label="Close" className="text-muted">✕</button>
        </header>

        <div className="flex border-b border-border">
          {(['inbox', 'sent'] as Box[]).map((key) => (
            <button key={key} type="button" onClick={() => { setBox(key); setOpenId(null) }}
              className={`flex-1 border-b-2 py-2 text-xs font-bold capitalize ${
                box === key ? 'border-accent text-fg' : 'border-transparent text-muted'}`}>
              {key}
            </button>
          ))}
        </div>

        <input value={search} onChange={(e) => setSearch(e.target.value)}
          placeholder="Search person, request or words…" aria-label="Search messages"
          className="mx-3 mt-3 rounded-md border border-border bg-surface px-2 py-1.5 text-xs" />
        <div className="px-3 pt-2.5">
          <FilterChips pings={searched} filter={filter} onChange={setFilter} />
        </div>

        {openId ? (
          /* Following the request link closes the whole panel -- it must not
             sit over the page it just navigated to. */
          <PingDetail id={openId} onBack={() => setOpenId(null)} onNavigate={onClose} />
        ) : (
          <div className="flex-1 overflow-y-auto p-3">
            {shown.length === 0
              ? <p className="p-3 text-xs text-muted">Nothing here.</p>
              : shown.map((p) => <PingCard key={p.id} ping={p} box={box} onOpen={() => setOpenId(p.id)} />)}
          </div>
        )}
      </aside>

      {composing && <PingModal init={composing} onClose={() => setComposing(null)} />}
    </div>
  )
}
