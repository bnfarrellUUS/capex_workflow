import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { createUser, type UserInput } from '../../api/users'
import { listDivisions } from '../../api/divisions'
import { ApiError } from '../../api/client'
import { UserForm } from './UserForm'

export default function UserNewPage() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const { data: divisions = [] } = useQuery({ queryKey: ['divisions'], queryFn: listDivisions })
  const mutation = useMutation({
    mutationFn: (body: UserInput) => createUser(body),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['users'] }); navigate('/admin/users') },
  })
  const error = mutation.error instanceof ApiError ? mutation.error.message : mutation.error ? 'Failed.' : null

  return (
    <div>
      <h1 className="mb-4 text-2xl font-semibold text-brand-navy">Add user</h1>
      <UserForm divisions={divisions} pending={mutation.isPending} error={error}
        onSubmit={(body) => mutation.mutate(body)} />
    </div>
  )
}
