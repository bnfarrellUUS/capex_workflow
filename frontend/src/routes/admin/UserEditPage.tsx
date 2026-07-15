import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { listUsers, updateUser, resetUserPassword, deleteUser, type UserInput } from '../../api/users'
import { listDivisions } from '../../api/divisions'
import { ApiError } from '../../api/client'
import { UserForm } from './UserForm'
import { Button } from '../../components/ui/Button'

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

  const deleteMutation = useMutation({
    mutationFn: () => deleteUser(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['users'] }); navigate('/admin/users') },
  })
  const deleteError = deleteMutation.error instanceof ApiError ? deleteMutation.error.message : null

  const [resetMsg, setResetMsg] = useState<string | null>(null)
  const resetMutation = useMutation({
    mutationFn: () => resetUserPassword(id),
    onMutate: () => setResetMsg(null),
    onSuccess: () => setResetMsg('Password reset to the default. The user must choose a new one at next sign-in.'),
  })

  if (!user) return <p className="text-sm text-muted">Loading…</p>

  return (
    <div className="space-y-8">
      <div>
        <h1 className="mb-4 text-2xl font-semibold text-fg">Edit user: {user.name}</h1>
        <UserForm divisions={divisions} user={user} pending={mutation.isPending} error={error}
          onSubmit={(body) => mutation.mutate(body)} />
      </div>
      <div className="max-w-lg border-t border-border pt-6">
        <h2 className="mb-1 font-semibold text-fg">Reset password</h2>
        <p className="mb-2 text-sm text-muted">
          Sets the account back to the default password (Welcome@1); the user must choose
          their own at next sign-in.
        </p>
        <Button disabled={resetMutation.isPending}
          onClick={() => {
            if (window.confirm(`Reset ${user.email} to the default password?`)) resetMutation.mutate()
          }}>Reset to default password</Button>
        {resetMsg && <p className="mt-2 text-sm text-emerald-600 dark:text-emerald-400">{resetMsg}</p>}
        {resetMutation.error instanceof ApiError && (
          <p className="mt-2 text-sm text-red-600 dark:text-red-400" role="alert">{resetMutation.error.message}</p>
        )}
      </div>
      <div className="max-w-lg border-t border-border pt-6">
        <h2 className="mb-1 font-semibold text-fg">Delete user</h2>
        <p className="mb-2 text-sm text-muted">
          Permanently removes this user. Users with request or approval history can't be
          deleted — deactivate them instead.
        </p>
        <Button
          className="bg-red-600 text-white hover:bg-red-700"
          disabled={deleteMutation.isPending}
          onClick={() => {
            if (window.confirm(`Delete user "${user.email}"? This cannot be undone.`)) {
              deleteMutation.mutate()
            }
          }}
        >
          Delete user
        </Button>
        {deleteError && <p className="mt-2 text-sm text-red-600 dark:text-red-400" role="alert">{deleteError}</p>}
      </div>
    </div>
  )
}
