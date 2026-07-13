import { useEffect, useState } from 'react'
import { useParams, useNavigate, useLocation } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import { getRequest, createDraft, updateDraft, submitRequest, resubmitRequest } from '../api/requests'
import { listDivisions, type Division } from '../api/divisions'
import { useMe } from '../auth/useMe'
import { ApiError } from '../api/client'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Select } from '../components/ui/Select'
import { BrandCard } from '../components/ui/BrandCard'
import { AddIcon, DeleteIcon, SubmitIcon } from '../components/ActionIcons'
import type { RequestForm } from './wizard/types'
import { toForm, toPayload, blankForm, equipmentTotal } from './wizard/types'

const STEPS = ['Basic Info', 'Description', 'Effect on Ops', 'Equipment', 'Economic', 'Review']

type Setter = <K extends keyof RequestForm>(k: K, v: RequestForm[K]) => void

const today = () => new Date().toISOString().slice(0, 10)

export default function WizardPage() {
  const { id: routeId } = useParams()
  const location = useLocation()
  const navigate = useNavigate()
  const { data: me } = useMe()
  // Existing draft: load it. New request (no id): stay unsaved until first save.
  const { data } = useQuery({
    queryKey: ['request', routeId],
    queryFn: () => getRequest(routeId!),
    enabled: !!routeId,
  })
  const { data: divisions = [] } = useQuery({ queryKey: ['divisions'], queryFn: listDivisions })
  const [form, setForm] = useState<RequestForm | null>(null)
  const [step, setStep] = useState<number>((location.state as { step?: number } | null)?.step ?? 0)
  const [saved, setSaved] = useState(false)

  const isNew = !routeId
  const isRejected = data?.status === 'REJECTED'

  // Seed the form once: from the loaded draft (edit) or a blank form (new).
  useEffect(() => {
    if (form) return
    if (routeId) { if (data) setForm(toForm(data)) }
    else if (me) setForm(blankForm(me.division_id ?? '', today()))
  }, [routeId, data, me, form])

  // Persist the form: for a new request this creates the draft first (so merely
  // opening the wizard writes nothing); for an existing draft it just updates.
  async function persist(): Promise<string> {
    if (routeId) {
      await updateDraft(routeId, toPayload(form!))
      return routeId
    }
    const created = await createDraft()
    await updateDraft(created.id, toPayload(form!))
    return created.id
  }

  const save = useMutation({
    mutationFn: persist,
    onSuccess: (savedId) => {
      setSaved(true)
      if (isNew) navigate(`/requests/${savedId}/edit`, { replace: true, state: { step } })
    },
  })
  const submit = useMutation({
    mutationFn: async () => {
      const theId = await persist()
      await (isRejected ? resubmitRequest(theId) : submitRequest(theId))
      return theId
    },
    onSuccess: (theId) => navigate(`/requests/${theId}`, { replace: true }),
  })
  const submitError = submit.error instanceof ApiError ? submit.error.message : null
  const saveError = save.error instanceof ApiError ? save.error.message : null

  // Existing drafts auto-save when moving between steps; a brand-new request
  // navigates locally and only persists on Save Draft / Submit.
  async function goToStep(i: number) {
    if (isNew) { setStep(i); return }
    try {
      await save.mutateAsync()
    } catch {
      return // error surfaced via saveError; stay put
    }
    setStep(i)
  }

  if (!form) return <p className="text-sm text-muted">Loading…</p>

  const set: Setter = (k, v) => { setForm({ ...form, [k]: v }); setSaved(false) }

  const stepper = (
    <ol className="flex items-center gap-1 overflow-x-auto border-b border-border bg-surface-2 px-7 py-3">
      {STEPS.map((label, i) => (
        <li key={label} className="flex min-w-0 items-center gap-1">
          {i > 0 && <span aria-hidden className="h-px w-4 shrink-0 bg-border sm:w-6" />}
          <button
            type="button"
            disabled={save.isPending}
            aria-current={i === step ? 'step' : undefined}
            onClick={() => { if (i !== step) goToStep(i) }}
            className="group flex items-center gap-2 rounded-full py-1 pl-1 pr-2.5 transition hover:bg-accent/10 disabled:opacity-60"
          >
            <span
              className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold transition ${
                i === step
                  ? 'bg-accent text-accent-fg ring-2 ring-accent/30'
                  : i < step
                    ? 'bg-accent/15 text-accent'
                    : 'border border-border bg-surface text-muted'
              }`}
            >
              {i < step ? '✓' : i + 1}
            </span>
            <span className={`whitespace-nowrap text-xs ${
              i === step ? 'font-semibold text-fg' : 'text-muted group-hover:text-fg'
            }`}>
              {label}
            </span>
          </button>
        </li>
      ))}
    </ol>
  )

  return (
    <div className="max-w-3xl">
      <BrandCard
        title={data ? `Request ${data.number}` : 'New Request'}
        subtitle="New Capital Request"
        mark="newRequest"
        subheader={stepper}
        footer={
          <>
            <Button variant="secondary"
              disabled={step === 0} onClick={() => setStep(step - 1)}>Back</Button>
            <Button variant="secondary"
              disabled={save.isPending} onClick={() => save.mutate()}>Save Draft</Button>
            {saved && !saveError && <span className="text-sm text-emerald-600 dark:text-emerald-400">Saved.</span>}
            {saveError && <span className="text-sm text-red-600 dark:text-red-400" role="alert">{saveError}</span>}
            <div className="flex-1" />
            {step < STEPS.length - 1 && (
              <Button disabled={save.isPending} onClick={() => goToStep(step + 1)}>Next</Button>
            )}
          </>
        }
      >
        {step === 0 && <BasicInfo form={form} set={set}
          number={data?.number} requestorName={data?.requestor_name ?? me?.name ?? ''}
          divisions={divisions} />}
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
          onSubmit={() => submit.mutate()}
          pending={submit.isPending || save.isPending} error={submitError}
          submitLabel={isRejected ? 'Resubmit for approval' : 'Submit for approval'} />}
      </BrandCard>
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
  ['lease_recommended', 'Recommended for lease rather than purchase (attach explanation & evaluation; note any manufacturer/dealer financing)'],
]

function BasicInfo({ form, set, number, requestorName, divisions }:
  { form: RequestForm; set: Setter; number?: string; requestorName: string; divisions: Division[] }) {
  const readOnlyClass = 'cursor-default bg-surface-2 text-muted'
  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-3">
        <Field label="Capital request no.">
          <Input value={number ?? '(assigned on save)'} readOnly className={readOnlyClass} />
        </Field>
        <Field label="Date">
          <Input type="date" value={form.request_date}
            onChange={(e) => set('request_date', e.target.value)} />
        </Field>
        <Field label="Requested by">
          <Input value={requestorName} readOnly className={readOnlyClass} />
        </Field>
      </div>
      <Field label="Equipment / project description">
        <textarea className="min-h-24 w-full rounded-md border border-border bg-surface p-2 text-sm text-fg outline-none focus:border-accent"
          value={form.description} onChange={(e) => set('description', e.target.value)} />
      </Field>
      <Field label="Division">
        <Select value={form.division_id} onChange={(e) => set('division_id', e.target.value)}>
          <option value="">— Select division —</option>
          {divisions.map((d) => (
            <option key={d.id} value={d.id}>{d.number} — {d.name}</option>
          ))}
        </Select>
      </Field>
      <fieldset>
        <legend className="mb-1.5 text-sm font-medium">Flags</legend>
        <div className="grid gap-x-6 gap-y-1.5 sm:grid-cols-2">
          {FLAGS.map(([key, label], i) => (
            <label key={key}
              className={`flex items-start gap-2 text-sm ${i === FLAGS.length - 1 ? 'sm:col-span-2' : ''}`}>
              <input type="checkbox" className="mt-0.5" checked={form[key] as boolean}
                onChange={(e) => set(key, e.target.checked as never)} />
              {label}
            </label>
          ))}
        </div>
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
          <button className="inline-flex items-center gap-1 text-sm text-red-600 dark:text-red-400" onClick={() => remove(idx)}>
            <DeleteIcon size={15} />Remove
          </button>
        </div>
      ))}
      <button className="inline-flex items-center gap-1.5 text-sm text-accent" onClick={add}>
        <AddIcon size={16} />Add line item
      </button>
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

function Review({ form, onSubmit, pending, error, submitLabel }:
  { form: RequestForm; onSubmit: () => void; pending: boolean; error: string | null; submitLabel: string }) {
  const total = equipmentTotal(form.equipment_items)
  return (
    <div className="space-y-3 text-sm">
      <p><span className="font-medium">Description:</span> {form.description || '—'}</p>
      <p><span className="font-medium">Equipment lines:</span> {form.equipment_items.length}</p>
      <p><span className="font-medium">Total cost:</span> ${total.toLocaleString()}</p>
      {error && <p className="text-red-600 dark:text-red-400" role="alert">{error}</p>}
      <Button disabled={pending} onClick={onSubmit}><SubmitIcon size={16} />{submitLabel}</Button>
    </div>
  )
}
