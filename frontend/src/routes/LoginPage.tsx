import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { getAuthConfig, login } from '../api/auth'
import { safeNext } from '../auth/loginRedirect'
import { ApiError } from '../api/client'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { PasswordInput } from '../components/ui/PasswordInput'
import { Lockup } from '../components/Lockup'

/* Each message names WHO fixes it -- IT for a group or identity problem, an app
   admin for a missing or deactivated row, the user for a cancelled sign-in.
   That single detail removes most of the support traffic this feature would
   otherwise generate. Keys are sso_service.ERROR_CODES. */
export const SSO_ERRORS: Record<string, string> = {
  not_in_group:
    "Your Microsoft account isn't in the authorized security group. Contact IT to request access.",
  no_groups_claim:
    'Microsoft sign-in succeeded but no group information was returned. Contact IT.',
  unknown_user:
    "Your Microsoft account isn't set up in CAPRI yet. Ask an admin to add your user.",
  inactive_user: 'Your account is deactivated. Contact an admin.',
  identity_mismatch:
    "This Microsoft account doesn't match the account on file for your email address. Contact IT.",
  auth_failed: 'Microsoft sign-in failed or was cancelled. Please try again.',
}

/* Microsoft's mark keeps its official four colours, so it is inlined here
   rather than added to NavIcons/ActionIcons, which are currentColor line icons
   on a 24px grid. */
function MicrosoftMark() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true" className="shrink-0">
      <rect x="0" y="0" width="8" height="8" fill="#F25022" />
      <rect x="10" y="0" width="8" height="8" fill="#7FBA00" />
      <rect x="0" y="10" width="8" height="8" fill="#00A4EF" />
      <rect x="10" y="10" width="8" height="8" fill="#FFB900" />
    </svg>
  )
}

export default function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [ssoError, setSsoError] = useState<string | null>(null)
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const qc = useQueryClient()

  /* Tri-state, not boolean: SSO-on means SSO *only*, so rendering the password
     form before we know would flash a form that then disappears. isPending IS
     the third state, so no extra bookkeeping is needed. A failed call falls
     back to the password form, which at least gives a comprehensible error. */
  const { data: authConfig, isPending: configPending } = useQuery({
    queryKey: ['auth-config'], queryFn: getAuthConfig, retry: false,
  })
  const ssoEnabled = configPending ? null : (authConfig?.sso_enabled ?? false)

  /* Translate the code the callback redirected with, then strip it so a
     refresh does not resurrect a stale error. Any ?next= is preserved. */
  useEffect(() => {
    const code = searchParams.get('sso_error')
    if (!code) return
    setSsoError(SSO_ERRORS[code] ?? 'Microsoft sign-in failed.')
    const rest = new URLSearchParams(searchParams)
    rest.delete('sso_error')
    setSearchParams(rest, { replace: true })
  }, [searchParams, setSearchParams])

  const mutation = useMutation({
    mutationFn: () => login(email, password),
    onSuccess: (user) => {
      qc.setQueryData(['me'], user)
      navigate(user.must_change_password ? '/change-password' : safeNext(searchParams.get('next')),
        { replace: true })
    },
  })

  const error =
    ssoError ??
    (mutation.error instanceof ApiError
      ? mutation.error.message
      : mutation.error
        ? 'Login failed.'
        : null)

  function startSso() {
    const next = safeNext(searchParams.get('next'))
    // A top-level navigation, not a fetch: the browser has to follow the
    // redirect chain out to Entra and back.
    window.location.assign(`/api/auth/sso/login?next=${encodeURIComponent(next)}`)
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-bg p-4">
      <div className="w-full max-w-sm rounded-xl border border-border bg-surface p-6 shadow-sm">
        <div className="mb-6">
          {/* Left-justified, matching the brand lockup artwork. */}
          <Lockup
            panel
            markSize={72}
            subtitle="Capital Approval, Planning, Reporting & Investment"
            className="w-full"
          />
        </div>

        {error && (
          <p className="mb-4 text-sm text-red-600 dark:text-red-400" role="alert">{error}</p>
        )}

        {ssoEnabled === null && (
          <p className="text-sm text-muted">Loading sign-in options…</p>
        )}

        {ssoEnabled === true && (
          <Button type="button" className="w-full" onClick={startSso}>
            <MicrosoftMark />
            Sign in with Microsoft
          </Button>
        )}

        {ssoEnabled === false && (
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
            <Button type="submit" className="w-full" disabled={mutation.isPending}>
              {mutation.isPending ? 'Signing in…' : 'Sign in'}
            </Button>
          </form>
        )}
      </div>
    </main>
  )
}
