import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { createDivision, type DivisionInput } from '../../api/divisions'
import { listUsers } from '../../api/users'
import { ApiError } from '../../api/client'
import { DivisionForm } from './DivisionForm'

export default function DivisionNewPage() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const { data: users = [] } = useQuery({ queryKey: ['users'], queryFn: listUsers })
  const approvers = users.filter((u) => u.roles.includes('APPROVER'))
  const mutation = useMutation({
    mutationFn: (body: DivisionInput) => createDivision(body),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['divisions'] }); navigate('/admin/divisions') },
  })
  const error = mutation.error instanceof ApiError ? mutation.error.message : mutation.error ? 'Failed.' : null
  return (
    <div>
      <h1 className="mb-4 text-2xl font-semibold text-fg">Add division</h1>
      <DivisionForm approvers={approvers} pending={mutation.isPending} error={error}
        onSubmit={(body) => mutation.mutate(body)} />
    </div>
  )
}
