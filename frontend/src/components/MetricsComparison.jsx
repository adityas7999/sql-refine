import { Card, Col, Row } from 'react-bootstrap'

function score(value) {
  if (value === null || value === undefined) return { text: 'Unavailable', tone: 'neutral' }
  return { text: `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`, tone: value > 0 ? 'positive' : value < 0 ? 'negative' : 'neutral' }
}

export default function MetricsComparison({ metrics, mode, hasOptimized }) {
  if (!hasOptimized) return <Card className="tool-card"><Card.Header>Performance comparison</Card.Header><Card.Body><p className="text-secondary mb-0">No semantics-preserving rewrite was applied, so SQLRefine did not manufacture a comparison.</p></Card.Body></Card>
  const values = [['Measured time improvement', metrics.timeEfficiency], ['Estimated cost improvement', metrics.costEfficiency], ['Composite score', metrics.compositeScore]]
  return (
    <Card className="tool-card">
      <Card.Header>Performance comparison · {mode === 'runtime' ? 'measured + estimated' : 'estimated only'}</Card.Header>
      <Card.Body><Row className="g-3">{values.map(([label, value]) => { const display = score(value); return <Col md={4} key={label}><div className={`score-box ${display.tone}`}><span>{label}</span><strong>{display.text}</strong></div></Col> })}</Row>
        <p className="metric-note mb-0 mt-3">Measured time uses median wall-clock samples. Cost is MySQL's estimate. Negative values are regressions; unavailable values are never replaced with artificial numbers.</p>
      </Card.Body>
    </Card>
  )
}

