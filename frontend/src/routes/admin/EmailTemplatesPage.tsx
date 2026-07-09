import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { listEmailTemplates } from '../../api/emailTemplates'

export default function EmailTemplatesPage() {
  const { data = [] } = useQuery({ queryKey: ['email-templates'], queryFn: listEmailTemplates })
  return (
    <div className="max-w-3xl">
      <h1 className="mb-4 text-2xl font-semibold text-fg">Email Templates</h1>
      <p className="mb-4 text-sm text-muted">Customize the emails CAPEX Flow sends to users.</p>
      <div className="space-y-2">
        {data.map((t) => (
          <Link key={t.type} to={`/admin/email-templates/${t.type}`}
            className="flex items-center justify-between rounded-xl border border-border bg-surface p-4 shadow-sm hover:border-accent">
            <div>
              <div className="font-medium text-fg">{t.name}</div>
              <div className="text-xs text-muted">{t.subject}</div>
            </div>
            <div className="flex items-center gap-2 text-xs">
              {t.is_custom && <span className="text-accent">customized</span>}
              {!t.enabled && <span className="text-red-600 dark:text-red-400">disabled</span>}
            </div>
          </Link>
        ))}
      </div>
    </div>
  )
}
