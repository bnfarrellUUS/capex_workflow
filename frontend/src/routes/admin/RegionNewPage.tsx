import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { createRegion, type RegionInput } from '../../api/regions'
import { listUsers } from '../../api/users'
import { ApiError } from '../../api/client'
import { RegionForm } from './RegionForm'

export default function RegionNewPage() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const { data: users = [] } = useQuery({ queryKey: ['users'], queryFn: listUsers })
  const approvers = users.filter((u) => u.roles.includes('APPROVER'))
  const mutation = useMutation({
    mutationFn: (body: RegionInput) => createRegion(body),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['regions'] }); navigate('/admin/regions') },
  })
  const error = mutation.error instanceof ApiError ? mutation.error.message : mutation.error ? 'Failed.' : null
  return (
    <div>
      <h1 className="mb-4 text-2xl font-semibold text-fg">Add region</h1>
      <RegionForm approvers={approvers} pending={mutation.isPending} error={error}
        onSubmit={(body) => mutation.mutate(body)} />
    </div>
  )
}
