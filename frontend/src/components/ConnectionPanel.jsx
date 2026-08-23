import { useState } from 'react'
import { Alert, Button, Card, Col, Form, Row } from 'react-bootstrap'

const initial = {
  name: 'MySQL connection', host: '', port: 3306, username: '', password: '',
  database: '', sslEnabled: false, sslVerifyCertificate: true,
}

export default function ConnectionPanel({ connected, summary, onTest, onConnect, onDisconnect, busy }) {
  const [form, setForm] = useState(initial)
  const [notice, setNotice] = useState(null)
  const update = (field, value) => setForm((current) => ({ ...current, [field]: value }))

  async function run(action) {
    setNotice(null)
    try {
      const result = await action(form)
      if (action === onConnect) {
        setForm((current) => ({ ...current, password: '' }))
        setNotice({ type: 'success', text: 'Connected. The password is now held only in the backend session.' })
      } else {
        setNotice({ type: 'success', text: `Connection succeeded (${result.serverVersion}).` })
      }
    } catch (error) {
      setNotice({ type: 'danger', text: error.message })
    }
  }

  if (connected) return (
    <Card className="tool-card connection-card">
      <Card.Body className="d-flex flex-wrap gap-3 align-items-center justify-content-between">
        <div><span className="status-label"><i /> Connected</span><h2 className="connection-name">{summary.name}</h2><p>{summary.username}@{summary.host}:{summary.port}{summary.sslEnabled ? ' · TLS' : ''}</p></div>
        <Button variant="outline-danger" size="sm" onClick={onDisconnect}>Disconnect and forget credentials</Button>
      </Card.Body>
    </Card>
  )

  return (
    <Card className="tool-card connection-card">
      <Card.Header>Connect to MySQL</Card.Header>
      <Card.Body>
        <p className="security-copy">Credentials are sent only to this self-hosted backend and kept in expiring process memory. They are never placed in browser storage.</p>
        {notice && <Alert variant={notice.type}>{notice.text}</Alert>}
        <Form onSubmit={(event) => { event.preventDefault(); run(onConnect) }} autoComplete="off">
          <Row className="g-3">
            <Col md={6}><Form.Label>Connection name</Form.Label><Form.Control value={form.name} onChange={(event) => update('name', event.target.value)} /></Col>
            <Col md={6}><Form.Label>Host</Form.Label><Form.Control required value={form.host} onChange={(event) => update('host', event.target.value)} /></Col>
            <Col md={3}><Form.Label>Port</Form.Label><Form.Control required type="number" min="1" max="65535" value={form.port} onChange={(event) => update('port', Number(event.target.value))} /></Col>
            <Col md={4}><Form.Label>Username</Form.Label><Form.Control required autoComplete="username" value={form.username} onChange={(event) => update('username', event.target.value)} /></Col>
            <Col md={5}><Form.Label>Password</Form.Label><Form.Control type="password" autoComplete="new-password" value={form.password} onChange={(event) => update('password', event.target.value)} /></Col>
            <Col md={6}><Form.Label>Default database <span>(optional)</span></Form.Label><Form.Control value={form.database} onChange={(event) => update('database', event.target.value)} /></Col>
            <Col md={6} className="d-flex align-items-end gap-4 pb-2">
              <Form.Check label="Use TLS" checked={form.sslEnabled} onChange={(event) => update('sslEnabled', event.target.checked)} />
              <Form.Check label="Verify certificate" disabled={!form.sslEnabled} checked={form.sslVerifyCertificate} onChange={(event) => update('sslVerifyCertificate', event.target.checked)} />
            </Col>
          </Row>
          <div className="d-flex justify-content-end gap-2 mt-4">
            <Button variant="outline-light" disabled={busy} onClick={() => run(onTest)}>Test connection</Button>
            <Button type="submit" disabled={busy}>{busy ? 'Connecting…' : 'Connect securely'}</Button>
          </div>
        </Form>
      </Card.Body>
    </Card>
  )
}
