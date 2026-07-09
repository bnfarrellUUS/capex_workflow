import type { ButtonHTMLAttributes } from 'react'

type Variant = 'primary' | 'secondary' | 'ghost'

const VARIANTS: Record<Variant, string> = {
  primary: 'bg-accent text-accent-fg hover:opacity-90',
  secondary: 'border border-border bg-surface text-fg hover:bg-surface-2',
  ghost: 'text-fg hover:bg-surface-2',
}

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
}

export function Button({ className = '', variant = 'primary', ...props }: ButtonProps) {
  return (
    <button
      className={`inline-flex items-center justify-center gap-1.5 rounded-md px-4 py-2 text-sm font-semibold transition disabled:opacity-50 ${VARIANTS[variant]} ${className}`}
      {...props}
    />
  )
}
