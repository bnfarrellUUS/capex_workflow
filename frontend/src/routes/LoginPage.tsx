import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { login } from '../api/auth'
import { safeNext } from '../auth/loginRedirect'
import { ApiError } from '../api/client'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { PasswordInput } from '../components/ui/PasswordInput'
import { Logo } from '../components/Logo'

export default function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const qc = useQueryClient()

  const mutation = useMutation({
    mutationFn: () => login(email, password),
    onSuccess: (user) => {
      qc.setQueryData(['me'], user)
      navigate(user.must_change_password ? '/change-password' : safeNext(searchParams.get('next')),
        { replace: true })
    },
  })

  const error =
    mutation.error instanceof ApiError
      ? mutation.error.message
      : mutation.error
        ? 'Login failed.'
        : null

  return (
    <main className="flex min-h-screen items-center justify-center bg-bg p-4">
      <div className="w-full max-w-sm rounded-xl border border-border bg-surface p-6 shadow-sm">
        <div className="mb-6 flex flex-col items-center text-center">
          <Logo size={52} tile className="mb-3" />
          <div className="text-xl font-bold text-fg">United Uptime Services</div>
          <div className="text-sm text-muted">CAPEX Flow</div>
        </div>
        <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); mutation.mutate() }}>
          <div className="space-y-1">
            <label htmlFor="email" className="text-sm font-medium">Email</label>
            <Input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)}
              autoComplete="email" required />
          </div>
          <div className="space-y-1">
            <label htmlFor="password" className="text-sm font-medium">Password</label>
            <PasswordInput id="password" value={password}
              onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required />
          </div>
          {error && <p className="text-sm text-red-600 dark:text-red-400" role="alert">{error}</p>}
          <Button type="submit" className="w-full" disabled={mutation.isPending}>
            {mutation.isPending ? 'Signing in…' : 'Sign in'}
          </Button>
        </form>
      </div>
    </main>
  )
}
