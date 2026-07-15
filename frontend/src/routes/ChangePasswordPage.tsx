import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { logout, setPassword } from '../api/auth'
import { ApiError } from '../api/client'
import { Button } from '../components/ui/Button'
import { PasswordInput } from '../components/ui/PasswordInput'
import { Logo } from '../components/Logo'

export default function ChangePasswordPage() {
  const [newPassword, setNewPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [localError, setLocalError] = useState<string | null>(null)
  const navigate = useNavigate()
  const qc = useQueryClient()

  const mutation = useMutation({
    mutationFn: () => setPassword(newPassword),
    onSuccess: (user) => {
      qc.setQueryData(['me'], user)
      navigate('/', { replace: true })
    },
  })

  function submit(e: React.FormEvent) {
    e.preventDefault()
    if (newPassword.length < 8) { setLocalError('Password must be at least 8 characters.'); return }
    if (newPassword !== confirm) { setLocalError('Passwords do not match.'); return }
    setLocalError(null)
    mutation.mutate()
  }

  const error = localError
    ?? (mutation.error instanceof ApiError ? mutation.error.message
      : mutation.error ? 'Could not set the password.' : null)

  return (
    <main className="flex min-h-screen items-center justify-center bg-bg p-4">
      <div className="w-full max-w-sm rounded-xl border border-border bg-surface p-6 shadow-sm">
        <div className="mb-6 flex flex-col items-center text-center">
          <Logo size={52} tile className="mb-3" />
          <div className="text-xl font-bold text-fg">Set your new password</div>
          <div className="text-sm text-muted">
            Your account is using the default password — choose your own to continue.
          </div>
        </div>
        <form className="space-y-4" onSubmit={submit}>
          <div className="space-y-1">
            <label htmlFor="new-password" className="text-sm font-medium">New password</label>
            <PasswordInput id="new-password" value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)} autoComplete="new-password" required />
          </div>
          <div className="space-y-1">
            <label htmlFor="confirm-password" className="text-sm font-medium">Confirm new password</label>
            <PasswordInput id="confirm-password" value={confirm}
              onChange={(e) => setConfirm(e.target.value)} autoComplete="new-password" required />
          </div>
          {error && <p className="text-sm text-red-600 dark:text-red-400" role="alert">{error}</p>}
          <Button type="submit" className="w-full" disabled={mutation.isPending}>
            {mutation.isPending ? 'Saving…' : 'Set password'}
          </Button>
          <button type="button"
            className="w-full text-center text-sm text-muted hover:text-fg hover:underline"
            onClick={async () => { await logout(); navigate('/login', { replace: true }) }}>
            Sign out instead
          </button>
        </form>
      </div>
    </main>
  )
}
