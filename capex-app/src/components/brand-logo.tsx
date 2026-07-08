export function BrandLogo({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 64 64" fill="none" aria-hidden="true" className={className}>
      <path d="M15 44 L32 16 L49 44" stroke="currentColor" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M22 35 L42 35" stroke="currentColor" strokeWidth="5" strokeLinecap="round" />
      <path d="M11 55 Q37 60 54 37" stroke="currentColor" strokeWidth="4" fill="none" strokeLinecap="round" opacity="0.42" />
    </svg>
  );
}
