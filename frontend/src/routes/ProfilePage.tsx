import { useEffect, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getProfile, setDelegate, changePassword, listDelegateOptions } from '../api/profileApi'
import { ApiError } from '../api/client'
import { Button } from '../components/ui/Button'
import { PasswordInput } from '../components/ui/PasswordInput'
import { Select } from '../components/ui/Select'
import { BrandCard } from '../components/ui/BrandCard'

export default function ProfilePage() {
  const qc = useQueryClient()
  const { data: profile } = useQuery({ queryKey: ['profile'], queryFn: getProfile })
  const { data: options = [] } = useQuery({ queryKey: ['delegate-options'], queryFn: listDelegateOptions })

  const [delegate, setDelegateId] = useState('')
  useEffect(() => { setDelegateId(profile?.delegate_id ?? '') }, [profile])

  const delegateMutation = useMutation({
    mutationFn: () => setDelegate(delegate || null),
    onSuccess: (p) => qc.setQueryData(['profile'], p),
  })

  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [pwMsg, setPwMsg] = useState<string | null>(null)
  const pwMutation = useMutation({
    mutationFn: () => changePassword(current, next),
    onSuccess: () => { setPwMsg('Password changed.'); setCurrent(''); setNext('') },
  })
  const pwError = pwMutation.error instanceof ApiError ? pwMutation.error.message : null

  return (
    <div className="max-w-xl">
      <BrandCard title="My Profile"
        subtitle={profile ? `${profile.name} — ${profile.email}` : ''}
        bodyClassName="space-y-8 px-7 py-6">
      <section className="space-y-2">
        <h2 className="font-semibold text-fg">Out-of-office delegate</h2>
        <Select value={delegate} onChange={(e) => setDelegateId(e.target.value)}>
          <option value="">— None —</option>
          {options.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
        </Select>
        <Button disabled={delegateMutation.isPending} onClick={() => delegateMutation.mutate()}>Save delegate</Button>
        {delegateMutation.isSuccess && <p className="text-sm text-emerald-600 dark:text-emerald-400">Delegate saved.</p>}
      </section>

      <section className="space-y-2 border-t border-border pt-6">
        <h2 className="font-semibold text-fg">Change password</h2>
        <PasswordInput placeholder="Current password" value={current}
          onChange={(e) => setCurrent(e.target.value)} autoComplete="current-password" />
        <PasswordInput placeholder="New password (min 8)" value={next}
          onChange={(e) => setNext(e.target.value)} autoComplete="new-password" />
        {pwError && <p className="text-sm text-red-600 dark:text-red-400" role="alert">{pwError}</p>}
        {pwMsg && <p className="text-sm text-emerald-600 dark:text-emerald-400">{pwMsg}</p>}
        <Button disabled={next.length < 8 || pwMutation.isPending} onClick={() => pwMutation.mutate()}>Change password</Button>
      </section>
      </BrandCard>
    </div>
  )
}
