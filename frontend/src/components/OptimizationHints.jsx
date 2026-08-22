import { Badge, Card } from 'react-bootstrap'

export default function OptimizationHints({ hints }) {
  return (
    <Card className="tool-card">
      <Card.Header>Optimization insights</Card.Header>
      <Card.Body>
        {!hints?.length ? <p className="text-secondary mb-0">No optimizer rules were triggered.</p> : (
          <div className="insight-list">{hints.map((hint, index) => (
            <div className="insight" key={`${hint.rule}-${index}`}>
              <Badge bg={hint.applied ? 'primary' : 'secondary'}>{hint.applied ? 'Applied' : 'Suggestion'}</Badge>
              <div><strong>{hint.rule.replaceAll('-', ' ')}</strong><p>{hint.message}</p></div>
            </div>
          ))}</div>
        )}
      </Card.Body>
    </Card>
  )
}

