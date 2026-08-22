import { Table } from 'react-bootstrap'

const show = (value) => value === null || value === undefined ? '—' : value

export default function ExecutionPlan({ plan }) {
  if (!plan?.length) return <p className="text-secondary mb-0">No plan rows were returned.</p>
  return (
    <div className="table-responsive plan-table">
      <Table hover className="mb-0 align-middle">
        <thead><tr><th>Operation</th><th>Cost</th><th>Est. rows</th><th>Actual time</th><th>Rows</th><th>Loops</th></tr></thead>
        <tbody>{plan.map((row, index) => (
          <tr key={`${row.operation}-${index}`}>
            <td className="operation" style={{ paddingLeft: `${1 + (row.depth || 0) * 1.2}rem` }}>{row.depth ? '↳ ' : ''}{row.operation}</td>
            <td>{show(row.cost)}</td><td>{show(row.estimatedRows)}</td><td>{show(row.actualTime)}</td>
            <td>{show(row.actualRows)}</td><td>{show(row.loops)}</td>
          </tr>
        ))}</tbody>
      </Table>
    </div>
  )
}

