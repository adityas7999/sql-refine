import { Button, Card, Form } from 'react-bootstrap'

export default function QueryEditor({ query, setQuery, onSubmit, loading }) {
  return (
    <Card className="tool-card editor-card">
      <Card.Header className="d-flex justify-content-between align-items-center">
        <span>SQL workspace</span><span className="dialect">MYSQL 8+</span>
      </Card.Header>
      <Card.Body>
        <Form onSubmit={onSubmit}>
          <Form.Control
            as="textarea"
            className="sql-editor"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            spellCheck={false}
            aria-label="SQL query"
            placeholder="SELECT * FROM students WHERE YEAR(created_at) = 2025;"
          />
          <div className="d-flex justify-content-between align-items-center mt-3">
            <span className="small text-secondary">Only one SELECT statement is accepted.</span>
            <Button type="submit" disabled={loading || !query.trim()}>
              {loading ? 'Analyzing…' : 'Analyze & Optimize'}
            </Button>
          </div>
        </Form>
      </Card.Body>
    </Card>
  )
}

