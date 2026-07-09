import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import { getRequest, updateDraft, submitRequest } from '../api/requests'
import { ApiError } from '../api/client'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import type { RequestForm } from './wizard/types'
import { toForm, toPayload, equipmentTotal } from './wizard/types'

const STEPS = ['Basic Info', 'Description', 'Effect on Ops', 'Equipment', 'Economic', 'Review']

type Setter = <K extends keyof RequestForm>(k: K, v: RequestForm[K]) => void

export default function WizardPage() {
  const { id = '' } = useParams()
  const { data } = useQuery({ queryKey: ['request', id], queryFn: () => getRequest(id) })
  const [form, setForm] = useState<RequestForm | null>(null)
  const [step, setStep] = useState(0)
  const [saved, setSaved] = useState(false)

  useEffect(() => { if (data && !form) setForm(toForm(data)) }, [data, form])

  const navigate = useNavigate()
  const save = useMutation({
    mutationFn: () => updateDraft(id, toPayload(form!)),
    onSuccess: () => setSaved(true),
  })
  const submit = useMutation({
    mutationFn: () => submitRequest(id),
    onSuccess: () => navigate(`/requests/${id}`, { replace: true }),
  })
  const submitError = submit.error instanceof ApiError ? submit.error.message : null
  const saveError = save.error instanceof ApiError ? save.error.message : null

  // Save first; only advance / submit if the save actually persisted.
  async function saveThen(action?: () => void) {
    try {
      await save.mutateAsync()
    } catch {
      return // error surfaced via saveError; stay put
    }
    action?.()
  }

  if (!form || !data) return <p className="text-sm text-muted">Loading…</p>

  const set: Setter = (k, v) => { setForm({ ...form, [k]: v }); setSaved(false) }

  return (
    <div className="max-w-3xl">
      <h1 className="text-2xl font-semibold text-fg">Request {data.number}</h1>
      <ol className="my-4 flex flex-wrap gap-2 text-xs">
        {STEPS.map((label, i) => (
          <li key={label}>
            <button
              type="button"
              disabled={save.isPending}
              onClick={() => { if (i !== step) saveThen(() => setStep(i)) }}
              className={`rounded px-2 py-1 transition disabled:opacity-60 ${
                i === step
                  ? 'bg-accent text-accent-fg'
                  : 'bg-surface-2 text-muted hover:bg-accent/10 hover:text-fg'
              }`}
            >
              {i + 1}. {label}
            </button>
          </li>
        ))}
      </ol>

      <div className="rounded-xl border border-border bg-surface p-6 shadow-sm">
        {step === 0 && <BasicInfo form={form} set={set} />}
        {step === 1 && (
          <Field label="Brief description & justification">
            <textarea className="min-h-32 w-full rounded-md border border-border bg-surface p-2 text-sm text-fg outline-none focus:border-accent"
              value={form.justification} onChange={(e) => set('justification', e.target.value)} />
          </Field>
        )}
        {step === 2 && (
          <Field label="Effect on operations">
            <textarea className="min-h-32 w-full rounded-md border border-border bg-surface p-2 text-sm text-fg outline-none focus:border-accent"
              value={form.effect_on_operations} onChange={(e) => set('effect_on_operations', e.target.value)} />
          </Field>
        )}
        {step === 3 && <Equipment form={form} set={set} />}
        {step === 4 && <Economic form={form} set={set} />}
        {step === 5 && <Review form={form}
          onSubmit={() => saveThen(() => submit.mutate())}
          pending={submit.isPending || save.isPending} error={submitError} />}
      </div>

      <div className="mt-4 flex items-center gap-3">
        <Button variant="secondary"
          disabled={step === 0} onClick={() => setStep(step - 1)}>Back</Button>
        <Button variant="secondary"
          disabled={save.isPending} onClick={() => save.mutate()}>Save Draft</Button>
        {saved && !saveError && <span className="text-sm text-emerald-600 dark:text-emerald-400">Saved.</span>}
        {saveError && <span className="text-sm text-red-600 dark:text-red-400" role="alert">{saveError}</span>}
        <div className="flex-1" />
        {step < STEPS.length - 1 && (
          <Button disabled={save.isPending} onClick={() => saveThen(() => setStep(step + 1))}>Next</Button>
        )}
      </div>
    </div>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <label className="text-sm font-medium">{label}</label>
      {children}
    </div>
  )
}

const FLAGS: [keyof RequestForm, string][] = [
  ['budgeted', 'Budgeted'], ['replacement', 'Replacement equipment'],
  ['health_safety', 'Health & safety driven'], ['revenue_generating', 'Revenue generating'],
  ['environmental', 'Environmental / sustainability'], ['competitive_bids', 'Competitive bids received'],
  ['lease_recommended', 'Lease recommended'],
]

function BasicInfo({ form, set }: { form: RequestForm; set: Setter }) {
  return (
    <div className="space-y-4">
      <Field label="Equipment / project description">
        <Input value={form.description} onChange={(e) => set('description', e.target.value)} />
      </Field>
      <fieldset className="space-y-1">
        <legend className="text-sm font-medium">Flags</legend>
        {FLAGS.map(([key, label]) => (
          <label key={key} className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={form[key] as boolean}
              onChange={(e) => set(key, e.target.checked as never)} />
            {label}
          </label>
        ))}
      </fieldset>
    </div>
  )
}

function Equipment({ form, set }: { form: RequestForm; set: Setter }) {
  const items = form.equipment_items
  const update = (idx: number, patch: Partial<(typeof items)[number]>) =>
    set('equipment_items', items.map((it, i) => (i === idx ? { ...it, ...patch } : it)))
  const add = () =>
    set('equipment_items', [...items, { units: 1, condition: 'NEW', type: '', make: '', model: '', cost: '' }])
  const remove = (idx: number) => set('equipment_items', items.filter((_, i) => i !== idx))
  return (
    <div className="space-y-3">
      {items.map((it, idx) => (
        <div key={idx} className="flex flex-wrap items-end gap-2 border-b border-border pb-2">
          <LabeledInput label="Units" value={String(it.units)} onChange={(v) => update(idx, { units: Number(v) || 0 })} w="w-16" />
          <LabeledInput label="Type" value={it.type} onChange={(v) => update(idx, { type: v })} />
          <LabeledInput label="Make" value={it.make} onChange={(v) => update(idx, { make: v })} />
          <LabeledInput label="Model" value={it.model} onChange={(v) => update(idx, { model: v })} />
          <LabeledInput label="Cost" value={it.cost} onChange={(v) => update(idx, { cost: v })} w="w-28" />
          <button className="text-sm text-red-600 dark:text-red-400" onClick={() => remove(idx)}>Remove</button>
        </div>
      ))}
      <button className="text-sm text-accent" onClick={add}>+ Add line item</button>
      <div className="text-right font-semibold">Equipment total: ${equipmentTotal(items).toLocaleString()}</div>
    </div>
  )
}

function LabeledInput({ label, value, onChange, w = 'w-40' }:
  { label: string; value: string; onChange: (v: string) => void; w?: string }) {
  return (
    <div className={`space-y-1 ${w}`}>
      <label className="text-xs text-muted">{label}</label>
      <Input value={value} onChange={(e) => onChange(e.target.value)} />
    </div>
  )
}

function Economic({ form, set }: { form: RequestForm; set: Setter }) {
  const total = equipmentTotal(form.equipment_items)
  const annual = Number(form.annual_savings) || 0
  const autoPayback = annual > 0 ? (total / annual).toFixed(2) : ''
  return (
    <div className="grid grid-cols-2 gap-4">
      <LabeledInput label="Asset / project life" value={form.asset_life} onChange={(v) => set('asset_life', v)} w="" />
      <LabeledInput label="IRR after tax (%)" value={form.irr_after_tax} onChange={(v) => set('irr_after_tax', v)} w="" />
      <LabeledInput label="First-year EBIT" value={form.first_year_ebit} onChange={(v) => set('first_year_ebit', v)} w="" />
      <LabeledInput label="Annual savings" value={form.annual_savings} onChange={(v) => set('annual_savings', v)} w="" />
      <div className="space-y-1">
        <label className="text-xs text-muted">Payback (years) — auto: {autoPayback || '—'}</label>
        <Input value={form.payback_years} placeholder={autoPayback}
          onChange={(e) => set('payback_years', e.target.value)} />
      </div>
      <LabeledInput label="NPV of future savings" value={form.npv_savings} onChange={(v) => set('npv_savings', v)} w="" />
    </div>
  )
}

function Review({ form, onSubmit, pending, error }:
  { form: RequestForm; onSubmit: () => void; pending: boolean; error: string | null }) {
  const total = equipmentTotal(form.equipment_items)
  return (
    <div className="space-y-3 text-sm">
      <p><span className="font-medium">Description:</span> {form.description || '—'}</p>
      <p><span className="font-medium">Equipment lines:</span> {form.equipment_items.length}</p>
      <p><span className="font-medium">Total cost:</span> ${total.toLocaleString()}</p>
      {error && <p className="text-red-600 dark:text-red-400" role="alert">{error}</p>}
      <Button disabled={pending} onClick={onSubmit}>Submit for approval</Button>
    </div>
  )
}
