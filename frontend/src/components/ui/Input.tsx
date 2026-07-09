import type { InputHTMLAttributes } from 'react'

export function Input({ className = '', ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={`w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-fg outline-none placeholder:text-muted focus:border-accent ${className}`}
      {...props}
    />
  )
}
