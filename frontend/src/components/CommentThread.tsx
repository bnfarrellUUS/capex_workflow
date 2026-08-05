import { useState } from 'react'
import { addComment, type CapexRequestData } from '../api/requests'
import { ApiError } from '../api/client'
import { formatActionDate } from '../routes/formatDate'
import { Button } from './ui/Button'
import { CommentIcon } from './ActionIcons'

/**
 * The request's Q&A thread. Posting changes no workflow state — the request
 * stays with the same people at the same level — so an approver can ask a
 * question without having to reject.
 */
export function CommentThread({ req, onPosted }: {
  req: CapexRequestData
  onPosted: (updated: CapexRequestData) => void
}) {
  const [body, setBody] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  async function post() {
    setErr(null)
    setBusy(true)
    try {
      const updated = await addComment(req.id, body.trim())
      setBody('')
      onPosted(updated)
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : 'Could not post the comment.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <section>
      <h2 className="mb-1 flex items-center gap-1.5 font-semibold text-fg">
        <CommentIcon size={17} />Comments
      </h2>
      <ul className="space-y-2">
        {req.comments.map((c) => (
          <li key={c.id} className="rounded-md border border-border bg-surface-2 p-3 text-sm">
            <div className="mb-0.5 flex flex-wrap items-baseline gap-x-2">
              <span className="font-medium text-fg">{c.author_name ?? 'Unknown'}</span>
              <span className="text-xs text-muted">{formatActionDate(c.created_at)}</span>
            </div>
            <p className="whitespace-pre-wrap">{c.body}</p>
          </li>
        ))}
        {req.comments.length === 0 && <li className="text-sm text-muted">No comments yet.</li>}
      </ul>
      <div className="mt-2 space-y-2">
        <textarea
          className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-fg placeholder:text-muted focus:outline-none focus:ring-2 focus:ring-accent"
          rows={3}
          placeholder="Ask a question or answer one…"
          value={body}
          onChange={(e) => setBody(e.target.value)}
        />
        {err && <p className="text-sm text-red-600 dark:text-red-400" role="alert">{err}</p>}
        <Button disabled={busy || !body.trim()} onClick={post}>
          <CommentIcon size={16} />Post comment
        </Button>
      </div>
    </section>
  )
}
