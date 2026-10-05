// `columns`: [{ key, label, align, wrap }]. `rows`: plain objects, already
// formatted for display. `onRowClick(row)` is optional -- when given, rows
// become clickable (used by paginated lists that open a detail panel).
export function Table({ columns, rows, onRowClick }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-hairline">
      <table className="min-w-full text-sm">
        <thead className="bg-panel-raised">
          <tr>
            {columns.map((c) => (
              <th
                key={c.key}
                className={`px-3 py-2 font-medium text-ink-dim uppercase text-xs tracking-wide whitespace-nowrap ${c.align === 'right' ? 'text-right' : 'text-left'}`}
              >
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-hairline">
          {rows.map((row, i) => (
            <tr
              key={i}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
              className={`hover:bg-panel-raised/60 ${onRowClick ? 'cursor-pointer' : ''}`}
            >
              {columns.map((c) => (
                <td
                  key={c.key}
                  className={`px-3 py-2 text-ink font-mono ${c.wrap ? 'whitespace-normal min-w-[16rem]' : 'whitespace-nowrap'} ${c.align === 'right' ? 'text-right' : 'text-left'}`}
                >
                  {row[c.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
