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

export default function EmailTemplateEditor() {
  const { type = '' } = useParams()
  const qc = useQueryClient()
  const { data } = useQuery({ queryKey: ['email-templates', type], queryFn: () => getEmailTemplate(type) })
  const [subject, setSubject] = useState('')
  const [body, setBody] = useState('')
  const [enabled, setEnabled] = useState(true)
  const [dirty, setDirty] = useState(false)
  const [preview, setPreview] = useState<string | null>(null)
  const insertRef = useRef<(t: string) => void>(() => {})

  useEffect(() => {
    if (data) { setSubject(data.subject); setBody(data.body_html); setEnabled(data.enabled); setDirty(false) }
  }, [data])

  function apply(updated: EmailTemplate) {
    qc.setQueryData(['email-templates', type], updated)
    qc.invalidateQueries({ queryKey: ['email-templates'] })
    setDirty(false)
  }
  const save = useMutation({ mutationFn: () => saveEmailTemplate(type, { subject, body_html: body, enabled }), onSuccess: apply })
  const asDefault = useMutation({ mutationFn: () => saveAsDefault(type), onSuccess: apply })
  const reset = useMutation({ mutationFn: () => resetEmailTemplate(type), onSuccess: apply })
  const doPreview = useMutation({
    mutationFn: () => previewEmailTemplate(type, { subject, body_html: body }),
    onSuccess: (p) => setPreview(p.html),
  })

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
        <label className="mb-1 block text-xs text-muted">Subject</label>
        <Input value={subject} onChange={(e) => { setSubject(e.target.value); setDirty(true) }} />
        <label className="mb-1 mt-4 block text-xs text-muted">Body</label>
        <QuillEditor value={data.body_html} onChange={(html) => { setBody(html); setDirty(true) }}
          onReady={(insert) => (insertRef.current = insert)} />
        <label className="mt-4 flex items-center gap-2 text-sm text-fg">
          <input type="checkbox" checked={enabled} onChange={(e) => { setEnabled(e.target.checked); setDirty(true) }} />
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
