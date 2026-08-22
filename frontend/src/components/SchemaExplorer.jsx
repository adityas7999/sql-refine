import { useMemo, useState } from 'react'
import { Accordion, Badge, Form } from 'react-bootstrap'

export default function SchemaExplorer({ schema, loading, onUseTable }) {
  const [search, setSearch] = useState('')
  const tables = useMemo(() => (schema?.tables || []).filter((table) => {
    const terms = [table.name, ...table.columns.map((column) => column.name)].join(' ').toLowerCase()
    return terms.includes(search.toLowerCase())
  }), [schema, search])

  return (
    <aside className="schema-panel">
      <div className="panel-heading"><div><span>Schema explorer</span><strong>{schema?.database || 'No database'}</strong></div><Badge bg="secondary">{schema?.tables?.length || 0} tables</Badge></div>
      <div className="schema-search"><Form.Control value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search tables or columns" /></div>
      {loading && <p className="empty-state">Loading schema…</p>}
      {!loading && !schema && <p className="empty-state">Select a database to inspect its schema.</p>}
      {!loading && schema && !tables.length && <p className="empty-state">No matching tables.</p>}
      <Accordion flush alwaysOpen>{tables.map((table) => (
        <Accordion.Item eventKey={table.name} key={table.name}>
          <Accordion.Header><span className="table-icon">▦</span><span>{table.name}</span></Accordion.Header>
          <Accordion.Body>
            <button className="use-table" type="button" onClick={() => onUseTable(table)}>Create query from table</button>
            <div className="column-list">{table.columns.map((column) => (
              <div className="column-row" key={column.name}><span>{column.key === 'PRI' ? '◆ ' : ''}{column.name}</span><code>{column.columnType}</code></div>
            ))}</div>
            {!!table.indexes.length && <details><summary>Indexes ({table.indexes.length})</summary>{table.indexes.map((index) => <p key={index.name}><code>{index.name}</code> · {index.columns.map((column) => column.name).join(', ')}</p>)}</details>}
            {!!table.relationships.length && <details><summary>Relationships ({table.relationships.length})</summary>{table.relationships.map((relation) => <p key={`${relation.constraint}-${relation.column}`}><code>{relation.column}</code> → {relation.referencedTable}.{relation.referencedColumn}</p>)}</details>}
          </Accordion.Body>
        </Accordion.Item>
      ))}</Accordion>
      {(schema?.truncated?.tables || schema?.truncated?.columns) && <p className="schema-warning">Schema results were capped by server limits.</p>}
    </aside>
  )
}

