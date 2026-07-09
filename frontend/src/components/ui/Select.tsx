import type { SelectHTMLAttributes } from 'react'

export function Select({ className = '', ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      className={`w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-fg outline-none focus:border-accent ${className}`}
      {...props}
    />
  )
}
