import { useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { createDraft } from '../api/requests'

export default function NewRequestPage() {
  const navigate = useNavigate()
  const started = useRef(false)
  useEffect(() => {
    if (started.current) return
    started.current = true
    createDraft()
      .then((r) => navigate(`/requests/${r.id}/edit`, { replace: true }))
      .catch(() => navigate('/', { replace: true }))
  }, [navigate])
  return <p className="text-sm text-slate-500">Creating draft…</p>
}
