import { useQuery } from '@tanstack/react-query'
import { Fragment, useState } from 'react'

import { listPings } from '../api/pings'
import { BrandCard } from '../components/ui/BrandCard'
import { Button } from '../components/ui/Button'
import { SendIcon } from '../components/ActionIcons'
import { PingStatusPill, who } from '../components/PingCard'
import { PingDetail } from '../components/PingDetail'
import { PingModal, type PingInit } from '../components/PingModal'
import { FilterChips, haystack, matches, type Box, type Filter } from '../components/PingPanel'
import { formatActionDate } from './formatDate'

const TH ='border-b border-border bg-brand-sky/25 text-left text-xs uppercase tracking-wide text-brand-navy dark:bg-brand-sky/10 dark:text-brand-sky [&>th]:px-3 [&>th]:py-2 [&>th]:font-semibold'

/** The full page is a TABLE in CAPRI's RequestsTable idiom, not the panel's
 *  card list (spec section 8.3). Clicking a row expands the detail INLINE
 *  beneath it; clicking again collapses. */
export default function MessagesPage() {
  const [box, setBox] = useState<Box>('inbox')
  const [filter, setFilter] = useState<Filter>('open')
  const [search, setSearch] = useState('')
  const [openId, setOpenId] = useState<string | null>(null)
  const [composing, setComposing] = useState<PingInit | null>(null)

  const { data: pings = [], isLoading } = useQuery({
    queryKey: ['pings', 'list', box], queryFn: () => listPings(box),
  })

  const term = search.trim().toLowerCase()
  const searched = term ? pings.filter((p) => haystack(p).includes(term)) : pings
  const shown = searched.filter((p) => matches(p, filter))

  const controls = (
    <div className="space-y-3 border-b border-border bg-surface-2 px-7 py-3">
      <div role="tablist" aria-label="Mailbox" className="flex border-b border-border">
        {(['inbox', 'sent'] as Box[]).map((key) => (
          <button key={key} type="button" role="tab" aria-selected={box === key}
            onClick={() => { setBox(key); setOpenId(null) }}
            className={`flex-1 border-b-2 py-2 text-sm font-bold capitalize ${
              box === key ? 'border-accent text-fg' : 'border-transparent text-muted'}`}>
            {key}
          </button>
        ))}
      </div>
      <input value={search} onChange={(e) => setSearch(e.target.value)}
        placeholder="Search person, request or words…" aria-label="Search messages"
        className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-fg outline-none focus:border-accent" />
      <FilterChips pings={searched} filter={filter} onChange={setFilter} />
    </div>
  )

  return (
    <BrandCard title="Messages" subtitle="Pings between CAPRI users" mark="messages"
      actions={<Button size="sm" onClick={() => setComposing({})}><SendIcon size={14} />New Ping</Button>}
      subheader={controls} bodyClassName="px-0 py-0">
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className={TH}>
              <th>From / To</th><th>Ping</th><th>Request</th>
              <th className="text-right">Replies</th><th>Status</th><th>Last activity</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && <tr><td className="px-3 py-3 text-muted" colSpan={6}>Loading…</td></tr>}
            {!isLoading && shown.length === 0 && (
              <tr><td className="px-3 py-3 text-muted" colSpan={6}>Nothing here.</td></tr>
            )}
            {shown.map((p) => (
              <Fragment key={p.id}>
                <tr onClick={() => setOpenId(openId === p.id ? null : p.id)}
                  className={`cursor-pointer border-b border-border last:border-0 hover:bg-surface-2 ${
                    openId === p.id ? 'ring-1 ring-inset ring-accent' : ''}`}>
                  <td className={`whitespace-nowrap px-3 py-2.5 ${p.unread_for_me ? 'font-semibold' : ''}`}>
                    {p.unread_for_me && <span className="mr-1.5 inline-block h-1.5 w-1.5 rounded-full bg-accent align-middle" />}
                    {who(p, box)}
                  </td>
                  <td className="max-w-[340px] truncate px-3 py-2.5 text-fg">{p.note}</td>
                  <td className="px-3 py-2.5">
                    {p.request && (
                      <span className="rounded-md border border-border bg-surface-2 px-1.5 py-0.5 text-xs text-muted">
                        {p.request.number}
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-2.5 text-right tabular-nums text-muted">{p.reply_count}</td>
                  <td className="px-3 py-2.5"><PingStatusPill ping={p} /></td>
                  <td className="whitespace-nowrap px-3 py-2.5 text-muted">{formatActionDate(p.last_activity_at)}</td>
                </tr>
                {openId === p.id && (
                  <tr className="border-b border-border bg-surface-2/60">
                    <td colSpan={6} className="p-0">
                      <div className="max-w-[720px]"><PingDetail id={p.id} onBack={() => setOpenId(null)} /></div>
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
      {composing && <PingModal init={composing} onClose={() => setComposing(null)} />}
    </BrandCard>
  )
}
