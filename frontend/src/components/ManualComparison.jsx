import { Alert, Button, Card, Col, Form, Row, Table } from 'react-bootstrap'
import MetricsComparison from './MetricsComparison.jsx'
import QueryResult from './QueryResult.jsx'

function Preview({ title, preview }) {
  if (!preview) return null
  return <Card className="tool-card"><Card.Header>{title} · limited preview</Card.Header><Card.Body>
    <div className="plan-table table-responsive"><Table size="sm" striped className="mb-0">
      <thead><tr>{preview.columns.map((column, index) => <th key={index}>{column}</th>)}</tr></thead>
      <tbody>{preview.rows.map((row, index) => <tr key={index}>{row.map((value, column) => <td key={column}>{value === null ? <em>NULL</em> : value}</td>)}</tr>)}</tbody>
    </Table></div>
    <p className="metric-note mt-2 mb-0">At most {preview.rowLimit} rows, {preview.columnLimit} columns and {preview.cellCharacterLimit} characters per cell. {preview.truncatedColumns ? 'Additional columns hidden. ' : ''}This is not an equivalence check.</p>
  </Card.Body></Card>
}

export default function ManualComparison({ original, setOriginal, candidate, setCandidate, mode, setMode, confirmed, setConfirmed, preview, setPreview, previewConfirmed, setPreviewConfirmed, loading, disabled, onSubmit, result }) {
  return <div className="results-stack">
    <Card className="tool-card"><Card.Header>Compare two read-only queries</Card.Header><Card.Body>
      <p className="metric-note">Both statements use the active connection and database. Plans estimate cost without executing the SELECT. Runtime benchmarking executes both queries; a preview also executes them.</p>
      <Form onSubmit={onSubmit}>
        <Row className="g-3">
          <Col lg={6}><Form.Label htmlFor="compare-original">Original SQL</Form.Label><Form.Control as="textarea" id="compare-original" className="sql-editor" value={original} onChange={(event) => setOriginal(event.target.value)} placeholder="SELECT ..." required /></Col>
          <Col lg={6}><Form.Label htmlFor="compare-candidate">Candidate SQL</Form.Label><Form.Control as="textarea" id="compare-candidate" className="sql-editor" value={candidate} onChange={(event) => setCandidate(event.target.value)} placeholder="SELECT ..." required /></Col>
        </Row>
        <div className="analysis-controls">
          <div className="mode-tabs">
            <Form.Check type="radio" id="compare-plan" name="compare-mode" label="Plan only" checked={mode === 'plan'} onChange={() => { setMode('plan'); setConfirmed(false) }} />
            <Form.Check type="radio" id="compare-runtime" name="compare-mode" label="Runtime benchmark" checked={mode === 'runtime'} onChange={() => setMode('runtime')} />
          </div>
          <Button type="submit" disabled={disabled || loading || !original.trim() || !candidate.trim() || (mode === 'runtime' && !confirmed) || (preview && !previewConfirmed)}>{loading ? 'Comparing…' : 'Compare queries'}</Button>
        </div>
        {mode === 'runtime' && <Alert variant="warning" className="runtime-warning mt-3">EXPLAIN ANALYZE runs both queries repeatedly. Use an authorized read-only account and appropriate workload.<Form.Check className="mt-2" label="I authorize runtime execution of both queries" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} /></Alert>}
        <Form.Check className="mt-3" label="Show up to five output rows from each query" checked={preview} onChange={(event) => { setPreview(event.target.checked); setPreviewConfirmed(false) }} />
        {preview && <Alert variant="warning" className="runtime-warning mt-2">Preview executes both SELECT statements and returns client data to this browser. It is limited and cannot establish full output equivalence.<Form.Check className="mt-2" label="I authorize displaying sample rows from both queries" checked={previewConfirmed} onChange={(event) => setPreviewConfirmed(event.target.checked)} /></Alert>}
      </Form>
    </Card.Body></Card>
    {result && <>
      {result.warnings?.map((warning) => <Alert variant="warning" key={warning}>{warning}</Alert>)}
      <MetricsComparison metrics={result.metrics} mode={result.mode} hasOptimized />
      <div className="compare-results"><QueryResult title="Original query" result={result.original} accent="original" /><QueryResult title="Candidate query" result={result.candidate} accent="optimized" /></div>
      {result.previews && <div className="compare-results"><Preview title="Original" preview={result.previews.original} /><Preview title="Candidate" preview={result.previews.candidate} /></div>}
    </>}
  </div>
}
