import { useEffect, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  getEmailTemplate, saveEmailTemplate, saveAsDefault, resetEmailTemplate,
  previewEmailTemplate, type EmailTemplate,
} from '../../api/emailTemplates'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { QuillEditor } from '../../components/ui/QuillEditor'
import { Logo } from '../../components/Logo'

const EMAIL_FONT = 'Arial, Helvetica, sans-serif'

export default function EmailTemplateEditor() {
  const { type = '' } = useParams()
  const qc = useQueryClient()
  const { data } = useQuery({ queryKey: ['email-templates', type], queryFn: () => getEmailTemplate(type) })
  const [subject, setSubject] = useState('')
  const [body, setBody] = useState('')
  const [enabled, setEnabled] = useState(true)
  const [dirty, setDirty] = useState(false)
  const [status, setStatus] = useState<string | null>(null)
  const [preview, setPreview] = useState<string | null>(null)
  const insertRef = useRef<(t: string) => void>(() => {})

  useEffect(() => {
    if (data) { setSubject(data.subject); setBody(data.body_html); setEnabled(data.enabled); setDirty(false) }
  }, [data])

  function markDirty() {
    setDirty(true)
    setStatus(null)
  }
  function apply(message: string) {
    return (updated: EmailTemplate) => {
      // Merge over the cached template rather than replace it, so a response
      // missing a field can never blank out what the page renders from.
      qc.setQueryData(['email-templates', type], (prev: EmailTemplate | undefined) =>
        prev ? { ...prev, ...updated } : updated)
      qc.invalidateQueries({ queryKey: ['email-templates'], exact: true })
      setDirty(false)
      setStatus(message)
    }
  }
  const save = useMutation({ mutationFn: () => saveEmailTemplate(type, { subject, body_html: body, enabled }), onSuccess: apply('Saved.') })
  const asDefault = useMutation({ mutationFn: () => saveAsDefault(type), onSuccess: apply('Saved as default.') })
  const reset = useMutation({ mutationFn: () => resetEmailTemplate(type), onSuccess: apply('Reset to default.') })
  const doPreview = useMutation({
    mutationFn: () => previewEmailTemplate(type, { subject, body_html: body }),
    onSuccess: (p) => setPreview(p.html),
  })
  const failure = [save, asDefault, reset, doPreview].find((m) => m.error)?.error
  const errorText = failure instanceof Error ? failure.message : null

  if (!data) return null
  return (
    <div className="flex gap-4">
      <div className="min-w-0 flex-1">
        <div className="mb-4 flex items-center justify-between">
          <h1 className="text-2xl font-semibold text-fg">
            {data.name} {dirty && <span className="ml-2 rounded bg-amber-100 px-2 py-0.5 text-xs text-amber-800">edited</span>}
          </h1>
          <div className="flex gap-2">
            <Button disabled={save.isPending} onClick={() => save.mutate()}>Save</Button>
            <Button variant="secondary" onClick={() => asDefault.mutate()}>Save as Default</Button>
            <Button variant="secondary" onClick={() => doPreview.mutate()}>Preview</Button>
            <Button variant="ghost" onClick={() => reset.mutate()}>Reset to default</Button>
          </div>
        </div>
        {status && <p className="mb-2 text-sm text-emerald-600 dark:text-emerald-400">{status}</p>}
        {errorText && <p className="mb-2 text-sm text-red-600 dark:text-red-400" role="alert">{errorText}</p>}
        <label className="mb-1 block text-xs text-muted">Subject</label>
        <Input value={subject} onChange={(e) => { setSubject(e.target.value); markDirty() }} />
        <label className="mb-1 mt-4 block text-xs text-muted">Body</label>
        {/* Visual replica of the email frame so WYSIWYG editing matches what is
            sent: navy header + logo above the editable body, footer below. */}
        <div className="rounded-xl p-6" style={{ background: '#EEF3FB' }}>
          <div className="email-editor mx-auto max-w-[640px] overflow-hidden rounded-xl border bg-white"
            style={{ borderColor: '#E2E8F0' }}>
            <div className="flex items-center gap-3.5 px-7 py-5" style={{ background: '#0B2A4A' }}>
              <Logo size={40} />
              <div style={{ fontFamily: EMAIL_FONT }}>
                <div className="text-xl font-bold text-white">United Uptime Services</div>
                <div className="text-[13px] tracking-wide" style={{ color: '#93BBF5' }}>CAPEX Flow</div>
              </div>
            </div>
            <QuillEditor value={data.body_html} onChange={(html) => { setBody(html); markDirty() }}
              onReady={(insert) => (insertRef.current = insert)} />
            {/* Locked CTA button: rendered by the email frame below the body,
                shown here (non-editable) so the editor matches the sent email. */}
            <div className="px-7 pb-5">
              <span className="inline-block rounded-lg px-[22px] py-3 text-[15px] font-bold text-white"
                style={{ background: '#2563EB', fontFamily: EMAIL_FONT }}>
                {data.button_label}
              </span>
              <p className="mt-1.5 text-[11px]" style={{ color: '#94A3B8', fontFamily: EMAIL_FONT }}>
                Added automatically — links the reader to the request.
              </p>
            </div>
            <div className="px-7 py-4 text-xs" style={{
              borderTop: '1px solid #E2E8F0', color: '#64748B', fontFamily: EMAIL_FONT,
            }}>
              Automated message from CAPEX Flow — please do not reply.
            </div>
          </div>
        </div>
        <label className="mt-4 flex items-center gap-2 text-sm text-fg">
          <input type="checkbox" checked={enabled} onChange={(e) => { setEnabled(e.target.checked); markDirty() }} />
          Send this email
        </label>
      </div>
      <aside className="w-64 shrink-0 rounded-xl border border-border bg-surface-2 p-4">
        <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted">Placeholders</div>
        <p className="mb-3 text-xs text-muted">Click to insert. Replaced with real values when the email is sent.</p>
        <div className="space-y-2">
          {data.tokens.map((tok) => (
            <button key={tok.token} type="button" onClick={() => insertRef.current(tok.token)}
              className="block w-full text-left">
              <code className="text-accent">{tok.token}</code>
              <div className="text-xs text-muted">{tok.description}</div>
            </button>
          ))}
        </div>
      </aside>
      {preview !== null && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-6" onClick={() => setPreview(null)}>
          <div className="max-h-[90vh] w-full max-w-[680px] overflow-auto rounded-xl bg-white" onClick={(e) => e.stopPropagation()}>
            <iframe title="Email preview" srcDoc={preview} className="h-[80vh] w-full" sandbox="" />
          </div>
        </div>
      )}
    </div>
  )
}
