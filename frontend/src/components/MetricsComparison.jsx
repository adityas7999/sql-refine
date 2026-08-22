import { Card, Col, Row } from 'react-bootstrap'

function score(value) {
  if (value === null || value === undefined) return { text: 'Unavailable', tone: 'neutral' }
  return { text: `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`, tone: value > 0 ? 'positive' : value < 0 ? 'negative' : 'neutral' }
}

export default function MetricsComparison({ original, optimized, metrics }) {
  const items = [
    ['Time improvement', metrics.timeEfficiency],
    ['Cost improvement', metrics.costEfficiency],
    ['Composite score', metrics.compositeScore],
  ]
  return (
    <Card className="tool-card">
      <Card.Header>Performance comparison</Card.Header>
      <Card.Body>
        <Row className="g-3">
          <Col md={6}><div className="compare-box"><span>Original → optimized time</span><strong>{original.totalTimeMs ?? '—'} → {optimized.totalTimeMs ?? '—'} ms</strong></div></Col>
          <Col md={6}><div className="compare-box"><span>Original → optimized cost</span><strong>{original.plannerCost ?? '—'} → {optimized.plannerCost ?? '—'}</strong></div></Col>
          {items.map(([label, value]) => { const display = score(value); return (
            <Col md={4} key={label}><div className={`score-box ${display.tone}`}><span>{label}</span><strong>{display.text}</strong></div></Col>
          )})}
        </Row>
        <p className="metric-note mb-0 mt-3">Composite score = 60% time improvement + 40% cost improvement. Negative values are regressions.</p>
      </Card.Body>
    </Card>
  )
}

