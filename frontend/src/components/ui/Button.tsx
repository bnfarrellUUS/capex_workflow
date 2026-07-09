import type { ButtonHTMLAttributes } from 'react'

export function Button({ className = '', ...props }: ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      className={`inline-flex items-center justify-center rounded-md bg-brand-blue px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50 ${className}`}
      {...props}
    />
  )
}
