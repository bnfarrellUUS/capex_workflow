import { useState } from 'react'
import type { AdminUser, UserInput } from '../../api/users'
import type { Division } from '../../api/divisions'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'

const ALL_ROLES = ['REQUESTOR', 'APPROVER', 'FINANCE', 'ADMIN']

export function UserForm({
  divisions, user, pending, error, onSubmit,
}: {
  divisions: Division[]
  user?: AdminUser
  pending: boolean
  error: string | null
  onSubmit: (body: UserInput) => void
}) {
  const [username, setUsername] = useState(user?.username ?? '')
  const [name, setName] = useState(user?.name ?? '')
  const [email, setEmail] = useState(user?.email ?? '')
  const [password, setPassword] = useState('')
  const [roles, setRoles] = useState<string[]>(user?.roles ?? ['REQUESTOR'])
  const [divisionId, setDivisionId] = useState(user?.division_id ?? '')
  const [active, setActive] = useState(user?.active ?? true)

  function toggleRole(r: string) {
    setRoles((cur) => (cur.includes(r) ? cur.filter((x) => x !== r) : [...cur, r]))
  }

  function submit(e: React.FormEvent) {
    e.preventDefault()
    const body: UserInput = {
      email, name, roles, division_id: divisionId || null,
      ...(user ? { active } : { username, password }),
    }
    onSubmit(body)
  }

  return (
    <form onSubmit={submit} className="max-w-lg space-y-4">
      {!user && (
        <div className="space-y-1">
          <label className="text-sm font-medium">Username</label>
          <Input value={username} onChange={(e) => setUsername(e.target.value)} required />
        </div>
      )}
      <div className="space-y-1">
        <label className="text-sm font-medium">Full name</label>
        <Input value={name} onChange={(e) => setName(e.target.value)} required />
      </div>
      <div className="space-y-1">
        <label className="text-sm font-medium">Email</label>
        <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
      </div>
      {!user && (
        <div className="space-y-1">
          <label className="text-sm font-medium">Temporary password (min 8)</label>
          <Input type="text" minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} required />
        </div>
      )}
      <fieldset className="space-y-1">
        <legend className="text-sm font-medium">Roles</legend>
        {ALL_ROLES.map((r) => (
          <label key={r} className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={roles.includes(r)} onChange={() => toggleRole(r)} />
            {r.charAt(0) + r.slice(1).toLowerCase()}
          </label>
        ))}
      </fieldset>
      <div className="space-y-1">
        <label className="text-sm font-medium">Division</label>
        <Select value={divisionId} onChange={(e) => setDivisionId(e.target.value)}>
          <option value="">— None —</option>
          {divisions.map((d) => (
            <option key={d.id} value={d.id}>{d.number} — {d.name}</option>
          ))}
        </Select>
      </div>
      {user && (
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={active} onChange={(e) => setActive(e.target.checked)} /> Active
        </label>
      )}
      {error && <p className="text-sm text-red-600 dark:text-red-400" role="alert">{error}</p>}
      <Button type="submit" disabled={pending}>{user ? 'Save changes' : 'Create user'}</Button>
    </form>
  )
}
