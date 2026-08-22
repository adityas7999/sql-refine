import { useState } from 'react'
import { Alert, Form } from 'react-bootstrap'
import ConnectionPanel from './components/ConnectionPanel.jsx'
import Header from './components/Header.jsx'
import MetricsComparison from './components/MetricsComparison.jsx'
import OptimizationHints from './components/OptimizationHints.jsx'
import QueryEditor from './components/QueryEditor.jsx'
import QueryResult from './components/QueryResult.jsx'
import SchemaExplorer from './components/SchemaExplorer.jsx'
import { analyzeQuery, createConnectionSession, deleteConnectionSession, listDatabases, loadSchema, testConnection } from './services/api.js'

const quote = (identifier) => `\`${String(identifier).replaceAll('`', '``')}\``

export default function App() {
  const [sessionId, setSessionId] = useState(null)
  const [connection, setConnection] = useState(null)
  const [databases, setDatabases] = useState([])
  const [database, setDatabase] = useState('')
  const [schema, setSchema] = useState(null)
  const [query, setQuery] = useState('')
  const [mode, setMode] = useState('plan')
  const [runtimeConfirmed, setRuntimeConfirmed] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [schemaLoading, setSchemaLoading] = useState(false)

  async function connect(details) {
    setBusy(true); setError('')
    let created = null
    try {
      created = await createConnectionSession(details)
      const found = await listDatabases(created.sessionId)
      setSessionId(created.sessionId); setConnection(created.connection); setDatabases(found.databases)
      const preferred = found.databases.find((item) => item.name === created.connection.defaultDatabase) || found.databases.find((item) => !item.system) || found.databases[0]
      if (preferred) await selectDatabase(preferred.name, created.sessionId)
      return created
    } catch (requestError) {
      if (created?.sessionId) await deleteConnectionSession(created.sessionId).catch(() => {})
      throw requestError
    } finally { setBusy(false) }
  }

  async function selectDatabase(name, activeSession = sessionId) {
    setDatabase(name); setSchema(null); setResult(null); setSchemaLoading(true); setError('')
    try { setSchema(await loadSchema(activeSession, name)) }
    catch (requestError) { setError(requestError.message) }
    finally { setSchemaLoading(false) }
  }

  async function disconnect() {
    try { await deleteConnectionSession(sessionId) } catch { /* Backend may already have expired it. */ }
    setSessionId(null); setConnection(null); setDatabases([]); setDatabase(''); setSchema(null); setQuery(''); setResult(null); setRuntimeConfirmed(false)
  }

  async function submit(event) {
    event.preventDefault(); setBusy(true); setError(''); setResult(null)
    try { setResult(await analyzeQuery(sessionId, { query, database, mode, confirmRuntime: mode === 'runtime' && runtimeConfirmed })) }
    catch (requestError) {
      setError(requestError.message)
      if (requestError.status === 401) await disconnect()
    } finally { setBusy(false) }
  }

  function useTable(table) {
    setQuery(`SELECT *\nFROM ${quote(table.name)}\nLIMIT 100;`)
    setResult(null)
  }

  return (
    <><Header connected={Boolean(sessionId)} /><main className="container-fluid px-3 px-lg-4 py-4">
      <div className="workspace-intro mb-4"><p className="eyebrow">MYSQL QUERY LAB</p><h1>Inspect safely. Optimize deliberately.</h1><p>Connect to an authorized MySQL database, explore its schema, and separate estimated plans from measured execution.</p></div>
      <ConnectionPanel connected={Boolean(sessionId)} summary={connection} onTest={testConnection} onConnect={connect} onDisconnect={disconnect} busy={busy} />
      {error && <Alert variant="danger" className="mt-3" dismissible onClose={() => setError('')}>{error}</Alert>}
      {sessionId && <>
        <div className="database-bar mt-3"><Form.Label>Active database</Form.Label><Form.Select value={database} onChange={(event) => selectDatabase(event.target.value)}><option value="" disabled>Select a database</option>{databases.map((item) => <option key={item.name} value={item.name}>{item.name}{item.system ? ' (system)' : ''}</option>)}</Form.Select></div>
        <div className="workspace-grid mt-3"><SchemaExplorer schema={schema} loading={schemaLoading} onUseTable={useTable} /><section className="query-workspace">
          <QueryEditor query={query} setQuery={setQuery} onSubmit={submit} loading={busy} mode={mode} setMode={setMode} confirmed={runtimeConfirmed} setConfirmed={setRuntimeConfirmed} disabled={!database || schemaLoading} />
          {result && <div className="results-stack mt-3">
            {result.warnings?.map((warning) => <Alert variant="warning" key={warning}>{warning}</Alert>)}
            <MetricsComparison metrics={result.metrics} mode={result.mode} hasOptimized={Boolean(result.optimized)} />
            <OptimizationHints suggestions={result.suggestions} />
            <QueryResult title="Original query" result={result.original} accent="original" />
            <QueryResult title="Safe optimized query" result={result.optimized} accent="optimized" />
          </div>}
        </section></div>
      </>}
    </main></>
  )
}
