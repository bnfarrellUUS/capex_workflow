import { useState } from 'react'
import type { AdminUser, UserInput } from '../../api/users'
import type { Division } from '../../api/divisions'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { TransferList } from '../../components/ui/TransferList'

const ALL_ROLES = ['REQUESTOR', 'APPROVER', 'FINANCE', 'ADMIN']
const roleLabel = (r: string) => r.charAt(0) + r.slice(1).toLowerCase()

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

  function submit(e: React.FormEvent) {
    e.preventDefault()
    const body: UserInput = {
      username, email, name, roles, division_id: divisionId || null,
      ...(user ? { active } : { password }),
    }
    onSubmit(body)
  }

  return (
    <form onSubmit={submit} className="max-w-3xl space-y-4">
      <div className="space-y-1">
        <label className="text-sm font-medium">Username</label>
        <Input value={username} onChange={(e) => setUsername(e.target.value)} required />
      </div>
      <div className="space-y-1">
        <label className="text-sm font-medium">Full name</label>
        <Input value={name} onChange={(e) => setName(e.target.value)} required />
      </div>
      <div className="space-y-1">
        <label className="text-sm font-medium">Email</label>
        <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
      </div>
      {!user && (
        <div className="max-w-lg space-y-1">
          <label className="text-sm font-medium">Temporary password (min 8)</label>
          <Input type="text" minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} required />
        </div>
      )}
      <div className="space-y-1">
        <label className="text-sm font-medium">Roles</label>
        <TransferList
          options={ALL_ROLES.map((r) => ({ id: r, label: roleLabel(r) }))}
          selected={roles}
          onChange={setRoles}
          availableLabel="Available roles"
          selectedLabel="Assigned roles"
        />
      </div>
      <div className="max-w-lg space-y-1">
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
