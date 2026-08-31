import { useNavigate, useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { listRegions, updateRegion, type RegionInput } from '../../api/regions'
import { listUsers } from '../../api/users'
import { ApiError } from '../../api/client'
import { RegionForm } from './RegionForm'

export default function RegionEditPage() {
  const { id = '' } = useParams()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const { data: regions = [] } = useQuery({ queryKey: ['regions'], queryFn: listRegions })
  const { data: users = [] } = useQuery({ queryKey: ['users'], queryFn: listUsers })
  const approvers = users.filter((u) => u.roles.includes('APPROVER'))
  const region = regions.find((r) => r.id === id)

  const mutation = useMutation({
    mutationFn: (body: RegionInput) => updateRegion(id, body),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['regions'] }); navigate('/admin/regions') },
  })
  const error = mutation.error instanceof ApiError ? mutation.error.message : mutation.error ? 'Failed.' : null

  if (!region) return <p className="text-sm text-muted">Loading…</p>
  return (
    <div>
      <h1 className="mb-4 text-2xl font-semibold text-fg">Edit region: {region.name}</h1>
      <RegionForm approvers={approvers} region={region} pending={mutation.isPending} error={error}
        onSubmit={(body) => mutation.mutate(body)} />
    </div>
  )
}
