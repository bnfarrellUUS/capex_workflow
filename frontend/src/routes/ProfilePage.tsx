import { useEffect, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getProfile, setDelegate, changePassword, listDelegateOptions } from '../api/profileApi'
import { ApiError } from '../api/client'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Select } from '../components/ui/Select'

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
    <div className="max-w-lg space-y-8">
      <div>
        <h1 className="mb-4 text-2xl font-semibold text-fg">My Profile</h1>
        <p className="text-sm text-muted">{profile?.name} — {profile?.email}</p>
      </div>

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
        <Input type="password" placeholder="Current password" value={current}
          onChange={(e) => setCurrent(e.target.value)} autoComplete="current-password" />
        <Input type="password" placeholder="New password (min 8)" value={next}
          onChange={(e) => setNext(e.target.value)} autoComplete="new-password" />
        {pwError && <p className="text-sm text-red-600 dark:text-red-400" role="alert">{pwError}</p>}
        {pwMsg && <p className="text-sm text-emerald-600 dark:text-emerald-400">{pwMsg}</p>}
        <Button disabled={next.length < 8 || pwMutation.isPending} onClick={() => pwMutation.mutate()}>Change password</Button>
      </section>
    </div>
  )
}
