import { Badge, Card } from 'react-bootstrap'

const severityVariant = { critical: 'danger', warning: 'warning', info: 'info' }

export default function OptimizationHints({ suggestions }) {
  return (
    <Card className="tool-card">
      <Card.Header>Optimization suggestions</Card.Header>
      <Card.Body>
        {!suggestions?.length ? <p className="text-secondary mb-0">No optimization rules were triggered.</p> : <div className="insight-list">{suggestions.map((item, index) => (
          <div className={`insight severity-${item.severity}`} key={`${item.rule}-${index}`}>
            <div className="insight-badges"><Badge bg={item.applied ? 'success' : 'secondary'}>{item.applied ? 'Applied' : 'Not applied'}</Badge><Badge bg={severityVariant[item.severity] || 'secondary'} text={item.severity === 'warning' || item.severity === 'info' ? 'dark' : undefined}>{item.severity}</Badge><Badge bg="dark">{item.safety}</Badge></div>
            <div><strong>{item.rule.replaceAll('-', ' ')}</strong><p>{item.message}</p>{item.affectedSql && <code className="affected-sql">{item.affectedSql}</code>}</div>
          </div>
        ))}</div>}
      </Card.Body>
    </Card>
  )
}

