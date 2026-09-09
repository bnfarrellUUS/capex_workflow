import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { createPing, pingDirectory, pingSuggestions, type DirectoryUser } from '../api/pings'
import { Button } from './ui/Button'
import { SendIcon } from './ActionIcons'

export interface PingInit {
  recipientIds?: string[]
  /** The request this ping is about; the chip shows the number and can be cleared. */
  request?: { id: string; number: string } | null
}

const MAX_RECIPIENTS = 25 // mirrors ping_service.MAX_RECIPIENTS

/** One shared modal behind every entry point (spec section 8.5); an entry
 *  point differs only in the `init` it passes. */
export function PingModal({ init, onClose }: { init: PingInit; onClose: () => void }) {
  const qc = useQueryClient()
  const [selected, setSelected] = useState<string[]>(init.recipientIds ?? [])
  const [request, setRequest] = useState(init.request ?? null)
  const [note, setNote] = useState('')
  const [search, setSearch] = useState('')
  const [error, setError] = useState('')

  const { data: users = [] } = useQuery({ queryKey: ['pings', 'directory'], queryFn: pingDirectory })
  const { data: suggested = [] } = useQuery({
    queryKey: ['pings', 'suggestions', request?.id],
    queryFn: () => pingSuggestions(request!.id),
    enabled: !!request,
  })

  const send = useMutation({
    mutationFn: () => createPing({ recipient_ids: selected, note, request_id: request?.id ?? null }),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ['pings'] }); onClose() },
    onError: (err: Error) => setError(err.message),
  })

  const term = search.trim().toLowerCase()
  const matches = (u: DirectoryUser) => u.name.toLowerCase().includes(term)
  const suggestedShown = term ? suggested.filter(matches) : suggested
  const suggestedIds = new Set(suggested.map((u) => u.id))
  const rest = users.filter((u) => !suggestedIds.has(u.id))
  const shown = term ? rest.filter(matches) : rest

  const toggle = (id: string) =>
    setSelected((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]))

  return (
    <div className="fixed inset-0 z-[1500] flex items-center justify-center bg-black/50 p-4">
      <div role="dialog" aria-modal="true" aria-label="New ping"
        className="flex max-h-[80vh] w-[520px] max-w-full flex-col rounded-lg border border-border bg-surface">
        <header className="flex items-center gap-2 border-b border-border px-4 py-3">
          <span className="flex-1 text-sm font-bold">🔔 New Ping</span>
          <button type="button" onClick={onClose} aria-label="Close" className="text-muted">✕</button>
        </header>

        <div className="min-h-0 flex-1 overflow-y-auto p-4">
          <label className="mb-1 block text-xs font-semibold uppercase tracking-wider text-muted">To</label>
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search people…"
            className="mb-2 w-full rounded-md border border-border bg-surface px-2 py-1.5 text-sm" />
          <div className="mb-4 max-h-40 overflow-y-auto rounded-md border border-border">
            {suggestedShown.length > 0 && (
              <>
                <div className="px-2 py-1 text-[11px] font-semibold uppercase tracking-wider text-muted">Suggested</div>
                {suggestedShown.map((u) => <UserRow key={u.id} user={u} selected={selected} toggle={toggle} />)}
              </>
            )}
            {shown.map((u) => <UserRow key={u.id} user={u} selected={selected} toggle={toggle} />)}
          </div>

          {request && (
            <>
              <label className="mb-1 block text-xs font-semibold uppercase tracking-wider text-muted">Request</label>
              <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-border px-2.5 py-0.5 text-xs">
                <span>{request.number}</span>
                <button type="button" onClick={() => setRequest(null)} aria-label="Remove request"
                  className="text-muted hover:text-fg">✕</button>
              </div>
            </>
          )}

          <label className="mb-1 block text-xs font-semibold uppercase tracking-wider text-muted">Note</label>
          <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={5}
            className="w-full rounded-md border border-border bg-surface px-2 py-1.5 text-sm" />

          {error && <p role="alert" className="mt-2 text-xs text-red-700 dark:text-red-300">{error}</p>}
        </div>

        <footer className="flex items-center gap-2 border-t border-border px-4 py-3">
          <span className="flex-1 text-xs text-muted tabular-nums">{selected.length}/{MAX_RECIPIENTS} recipients</span>
          <Button variant="secondary" size="sm" onClick={onClose}>Cancel</Button>
          <Button size="sm" disabled={send.isPending || !note.trim() || selected.length === 0}
            onClick={() => send.mutate()}>
            <SendIcon size={14} />
            {send.isPending ? 'Sending…' : 'Send'}
          </Button>
        </footer>
      </div>
    </div>
  )
}

function UserRow({ user, selected, toggle }: {
  user: DirectoryUser; selected: string[]; toggle: (id: string) => void
}) {
  return (
    <label className="flex cursor-pointer items-center gap-2 px-2 py-1 text-sm hover:bg-surface-2">
      <input type="checkbox" checked={selected.includes(user.id)} onChange={() => toggle(user.id)} />
      <span className="flex-1">{user.name}</span>
      <span className="text-xs text-muted">{user.roles.join(', ')}</span>
    </label>
  )
}
