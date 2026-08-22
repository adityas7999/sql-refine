import { Alert, Button, Form } from 'react-bootstrap'

export default function AnalysisControls({ mode, setMode, confirmed, setConfirmed, loading, disabled }) {
  return (
    <div className="analysis-controls">
      <div className="mode-tabs">
        <Form.Check type="radio" id="mode-plan" name="mode" label="Plan only" checked={mode === 'plan'} onChange={() => { setMode('plan'); setConfirmed(false) }} />
        <Form.Check type="radio" id="mode-runtime" name="mode" label="Runtime benchmark" checked={mode === 'runtime'} onChange={() => setMode('runtime')} />
      </div>
      {mode === 'runtime' && <Alert variant="warning" className="runtime-warning"><strong>Execution warning:</strong> EXPLAIN ANALYZE runs the query multiple times. Use only a read-only account and non-production workload.<Form.Check className="mt-2" label="I understand and explicitly authorize runtime execution" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} /></Alert>}
      <Button type="submit" disabled={disabled || loading || (mode === 'runtime' && !confirmed)}>{loading ? 'Analyzing…' : mode === 'plan' ? 'Generate execution plan' : 'Run confirmed benchmark'}</Button>
    </div>
  )
}

