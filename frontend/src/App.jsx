import { useState } from 'react'
import { Alert } from 'react-bootstrap'
import Header from './components/Header.jsx'
import MetricsComparison from './components/MetricsComparison.jsx'
import OptimizationHints from './components/OptimizationHints.jsx'
import QueryEditor from './components/QueryEditor.jsx'
import QueryResult from './components/QueryResult.jsx'
import { compareQuery } from './services/api.js'

const EXAMPLE = `SELECT *
FROM students
WHERE YEAR(created_at) = 2025
ORDER BY name;`

export default function App() {
  const [query, setQuery] = useState(EXAMPLE)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function submit(event) {
    event.preventDefault(); setError(''); setLoading(true)
    try { setResult(await compareQuery(query)) }
    catch (requestError) { setResult(null); setError(requestError.message) }
    finally { setLoading(false) }
  }

  return (
    <><Header /><main className="container-xl py-4 py-lg-5">
      <div className="workspace-intro mb-4"><p className="eyebrow">QUERY LAB</p><h1>Inspect the plan. Refine the query.</h1><p>Compare rule-based rewrites against MySQL's measured execution plan.</p></div>
      <QueryEditor query={query} setQuery={setQuery} onSubmit={submit} loading={loading} />
      {error && <Alert variant="danger" className="mt-4" dismissible onClose={() => setError('')}>{error}</Alert>}
      {result && <div className="results-stack mt-4">
        <MetricsComparison original={result.original} optimized={result.optimized} metrics={result.metrics} />
        <OptimizationHints hints={result.hints} />
        <QueryResult title="Original query" result={result.original} accent="original" />
        <QueryResult title="Optimized query" result={result.optimized} accent="optimized" />
      </div>}
    </main></>
  )
}

