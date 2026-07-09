import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { listUsers, updateUser, resetUserPassword, type UserInput } from '../../api/users'
import { listDivisions } from '../../api/divisions'
import { ApiError } from '../../api/client'
import { UserForm } from './UserForm'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'

export default function UserEditPage() {
  const { id = '' } = useParams()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const { data: users = [] } = useQuery({ queryKey: ['users'], queryFn: listUsers })
  const { data: divisions = [] } = useQuery({ queryKey: ['divisions'], queryFn: listDivisions })
  const user = users.find((u) => u.id === id)

  const mutation = useMutation({
    mutationFn: (body: UserInput) => updateUser(id, body),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['users'] }); navigate('/admin/users') },
  })
  const error = mutation.error instanceof ApiError ? mutation.error.message : mutation.error ? 'Failed.' : null

  const [newPassword, setNewPassword] = useState('')
  const [resetMsg, setResetMsg] = useState<string | null>(null)
  const resetMutation = useMutation({
    mutationFn: () => resetUserPassword(id, newPassword),
    onSuccess: () => { setResetMsg('Password reset.'); setNewPassword('') },
  })

  if (!user) return <p className="text-sm text-slate-500">Loading…</p>

  return (
    <div className="space-y-8">
      <div>
        <h1 className="mb-4 text-2xl font-semibold text-brand-navy">Edit user: {user.username}</h1>
        <UserForm divisions={divisions} user={user} pending={mutation.isPending} error={error}
          onSubmit={(body) => mutation.mutate(body)} />
      </div>
      <div className="max-w-lg border-t pt-6">
        <h2 className="mb-2 font-semibold">Reset password</h2>
        <div className="flex items-end gap-2">
          <div className="flex-1">
            <Input type="text" minLength={8} placeholder="New temporary password"
              value={newPassword} onChange={(e) => setNewPassword(e.target.value)} />
          </div>
          <Button disabled={newPassword.length < 8 || resetMutation.isPending}
            onClick={() => resetMutation.mutate()}>Reset</Button>
        </div>
        {resetMsg && <p className="mt-2 text-sm text-green-700">{resetMsg}</p>}
      </div>
    </div>
  )
}
