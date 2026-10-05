export function Card({ title, subtitle, children, className = '' }) {
  return (
    <div className={`bg-panel rounded-lg border border-hairline p-5 ${className}`}>
      {title && <h3 className="text-base font-semibold text-ink">{title}</h3>}
      {subtitle && <p className="text-sm text-ink-dim mt-1 mb-3">{subtitle}</p>}
      <div className={title && !subtitle ? 'mt-3' : ''}>{children}</div>
    </div>
  )
}
