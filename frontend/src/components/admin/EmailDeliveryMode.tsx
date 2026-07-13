import { useEffect, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getEmailSettings, saveEmailSettings, type EmailSettings } from '../../api/emailTemplates'
import { Button } from '../ui/Button'
import { Input } from '../ui/Input'

const LIVE_CONFIRM =
  'Switch to Live mode?\n\nReal notification emails will be sent to actual recipients ' +
  '(approvers, requestors, finance). Continue?'

/**
 * Admin control for the email delivery mode. Test mode redirects every
 * notification to a single test recipient; Live mode sends to the real people.
 * Shown on both the Email Templates list page and the editor.
 */
export function EmailDeliveryMode() {
  const qc = useQueryClient()
  const { data } = useQuery({ queryKey: ['email-settings'], queryFn: getEmailSettings })
  const [mode, setMode] = useState<EmailSettings['mode']>('test')
  const [recipient, setRecipient] = useState('')
  const [status, setStatus] = useState<string | null>(null)

  useEffect(() => {
    if (data) { setMode(data.mode); setRecipient(data.test_recipient) }
  }, [data])

  const save = useMutation({
    mutationFn: (body: EmailSettings) => saveEmailSettings(body),
    onSuccess: (saved) => {
      qc.setQueryData(['email-settings'], saved)
      setStatus(saved.mode === 'live' ? 'Live — sending to real recipients.' : 'Saved.')
    },
  })

  function switchMode(next: EmailSettings['mode']) {
    if (next === mode) return
    if (next === 'live' && !window.confirm(LIVE_CONFIRM)) return
    setMode(next)
    setStatus(null)
    save.mutate({ mode: next, test_recipient: recipient })
  }

  if (!data) return null

  return (
    <div className="mb-4 rounded-xl border border-border bg-surface-2 p-4">
      <div className="flex flex-wrap items-center gap-3">
        <span className="text-sm font-semibold text-fg">Email delivery</span>
        <div className="inline-flex rounded-md border border-border bg-surface p-0.5">
          {(['test', 'live'] as const).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => switchMode(m)}
              disabled={save.isPending}
              className={`rounded px-3 py-1 text-sm font-medium transition ${
                mode === m
                  ? m === 'live'
                    ? 'bg-red-600 text-white'
                    : 'bg-accent text-accent-fg'
                  : 'text-muted hover:text-fg'
              }`}
            >
              {m === 'test' ? 'Test' : 'Live'}
            </button>
          ))}
        </div>
        {status && <span className="text-sm text-emerald-600 dark:text-emerald-400">{status}</span>}
      </div>

      {mode === 'test' ? (
        <div className="mt-3 flex flex-wrap items-end gap-2">
          <label className="text-xs text-muted">
            Test recipient — all notifications are redirected here
            <Input
              value={recipient}
              onChange={(e) => { setRecipient(e.target.value); setStatus(null) }}
              className="mt-1 w-72"
            />
          </label>
          <Button
            variant="secondary"
            disabled={save.isPending}
            onClick={() => { setStatus(null); save.mutate({ mode: 'test', test_recipient: recipient }) }}
          >
            Save
          </Button>
        </div>
      ) : (
        <p className="mt-2 text-sm text-muted">
          Notifications are sent to their real recipients. Switch to Test to redirect them to a single address.
        </p>
      )}
      {save.error && (
        <p className="mt-2 text-sm text-red-600 dark:text-red-400" role="alert">
          {save.error instanceof Error ? save.error.message : 'Save failed.'}
        </p>
      )}
    </div>
  )
}
