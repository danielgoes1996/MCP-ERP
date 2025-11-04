import { ReactNode } from 'react'

type Column = {
  id: string
  header: ReactNode
  align?: 'left' | 'right'
  render: (row: any) => ReactNode
}

type DataTableProps<T> = {
  columns: Column[]
  data: T[]
  loading?: boolean
  empty?: { icon?: ReactNode; message: ReactNode; action?: ReactNode }
}

export function DataTable<T = Record<string, unknown>>({ columns, data, loading = false, empty }: DataTableProps<T>) {
  const isEmpty = !loading && data.length === 0

  return (
    <div className="data-table">
      <div className="data-table__wrapper">
        <table>
          <thead>
            <tr>
              {columns.map((column) => (
                <th key={column.id} className={column.align === 'right' ? 'is-numeric' : ''} scope="col">
                  {column.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              [...Array(6)].map((_, index) => (
                <tr key={`skeleton-${index}`} className="animate-pulse">
                  {columns.map((column) => (
                    <td key={column.id} className={column.align === 'right' ? 'is-numeric' : ''}>
                      <div className="h-4 bg-gray-200 rounded" />
                    </td>
                  ))}
                </tr>
              ))
            ) : (
              data.map((row, rowIndex) => (
                <tr key={rowIndex}>
                  {columns.map((column) => (
                    <td key={column.id} className={column.align === 'right' ? 'is-numeric' : ''}>
                      {column.render(row)}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {isEmpty && empty ? (
        <div className="data-table__empty">
          {empty.icon ? <span className="data-table__empty-icon" aria-hidden="true">{empty.icon}</span> : null}
          <p>{empty.message}</p>
          {empty.action ? empty.action : null}
        </div>
      ) : null}
    </div>
  )
}
