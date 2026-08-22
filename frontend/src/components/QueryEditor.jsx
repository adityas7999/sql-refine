import { Card, Form } from 'react-bootstrap'
import AnalysisControls from './AnalysisControls.jsx'

export default function QueryEditor({ query, setQuery, onSubmit, loading, mode, setMode, confirmed, setConfirmed, disabled }) {
  return (
    <Card className="tool-card editor-card">
      <Card.Header className="d-flex justify-content-between align-items-center"><span>SQL editor</span><span className="dialect">MYSQL</span></Card.Header>
      <Card.Body>
        <Form onSubmit={onSubmit}>
          <Form.Control as="textarea" className="sql-editor" value={query} onChange={(event) => setQuery(event.target.value)} spellCheck={false} aria-label="SQL query" placeholder="Select a table from the schema explorer or write one read-only SELECT query." />
          <p className="editor-policy">One SELECT statement only. Comments, locking clauses, file operations, and dangerous functions are rejected by the backend AST policy.</p>
          <AnalysisControls mode={mode} setMode={setMode} confirmed={confirmed} setConfirmed={setConfirmed} loading={loading} disabled={disabled || !query.trim()} />
        </Form>
      </Card.Body>
    </Card>
  )
}

