export default function Header({ connected }) {
  return (
    <header className="app-header border-bottom">
      <div className="container-fluid px-4 d-flex align-items-center justify-content-between py-3">
        <div><div className="brand">SQL<span>Refine</span></div><div className="small text-secondary">Self-hosted MySQL analysis console</div></div>
        <span className={`status-pill ${connected ? 'online' : ''}`}><span /> {connected ? 'Backend session active' : 'Not connected'}</span>
      </div>
    </header>
  )
}

