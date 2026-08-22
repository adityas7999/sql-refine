import { Card } from 'react-bootstrap'
import ExecutionPlan from './ExecutionPlan.jsx'

const number = (value, suffix = '') => value === null || value === undefined ? 'Unavailable' : `${Number(value).toFixed(3)}${suffix}`

export default function QueryResult({ title, result, accent }) {
  if (!result) return null
  return (
    <Card className={`tool-card result-card ${accent}`}>
      <Card.Header>{title}</Card.Header>
      <Card.Body>
        <pre className="query-code"><code>{result.query}</code></pre>
        <div className="stat-strip">
          <div><span>Estimated cost</span><strong>{number(result.estimatedCost)}</strong></div>
          <div><span>Measured median</span><strong>{number(result.runtime?.medianMs, ' ms')}</strong></div>
          <div><span>Runtime variance</span><strong>{number(result.runtime?.varianceMs2, ' ms²')}</strong></div>
          <div><span>Samples / warm-ups</span><strong>{result.runtime ? `${result.runtime.sampleCount} / ${result.runtime.warmupCount}` : 'Plan only'}</strong></div>
        </div>
        {result.runtime?.samplesMs && <p className="sample-line">Samples: {result.runtime.samplesMs.map((sample) => `${sample.toFixed(3)} ms`).join(' · ')}</p>}
        <h3 className="section-label mt-4">Execution plan</h3>
        <ExecutionPlan plan={result.plan} />
      </Card.Body>
    </Card>
  )
}

