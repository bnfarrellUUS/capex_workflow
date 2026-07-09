import { useNavigate, useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { listDivisions, updateDivision, type DivisionInput } from '../../api/divisions'
import { listUsers } from '../../api/users'
import { ApiError } from '../../api/client'
import { DivisionForm } from './DivisionForm'

export default function DivisionEditPage() {
  const { id = '' } = useParams()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const { data: divisions = [] } = useQuery({ queryKey: ['divisions'], queryFn: listDivisions })
  const { data: users = [] } = useQuery({ queryKey: ['users'], queryFn: listUsers })
  const approvers = users.filter((u) => u.roles.includes('APPROVER'))
  const division = divisions.find((d) => d.id === id)

  const mutation = useMutation({
    mutationFn: (body: DivisionInput) => updateDivision(id, body),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['divisions'] }); navigate('/admin/divisions') },
  })
  const error = mutation.error instanceof ApiError ? mutation.error.message : mutation.error ? 'Failed.' : null

  if (!division) return <p className="text-sm text-muted">Loading…</p>
  return (
    <div>
      <h1 className="mb-4 text-2xl font-semibold text-fg">Edit division: {division.number}</h1>
      <DivisionForm approvers={approvers} division={division} pending={mutation.isPending} error={error}
        onSubmit={(body) => mutation.mutate(body)} />
    </div>
  )
}
