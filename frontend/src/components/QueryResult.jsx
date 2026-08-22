import { Card } from 'react-bootstrap'
import ExecutionPlan from './ExecutionPlan.jsx'

const metric = (value, suffix = '') => value === null || value === undefined ? 'Unavailable' : `${Number(value).toFixed(3)}${suffix}`

export default function QueryResult({ title, result, accent }) {
  return (
    <Card className={`tool-card result-card ${accent}`}>
      <Card.Header>{title}</Card.Header>
      <Card.Body>
        <pre className="query-code"><code>{result.query}</code></pre>
        <div className="stat-strip">
          <div><span>Execution time</span><strong>{metric(result.totalTimeMs, ' ms')}</strong></div>
          <div><span>Planner cost</span><strong>{metric(result.plannerCost)}</strong></div>
          <div><span>Indexes detected</span><strong>{result.indexes?.join(', ') || 'None'}</strong></div>
        </div>
        <h3 className="section-label mt-4">Execution plan</h3>
        <ExecutionPlan plan={result.plan} />
      </Card.Body>
    </Card>
  )
}

