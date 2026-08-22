export default function Header() {
  return (
    <header className="app-header border-bottom">
      <div className="container-xl d-flex align-items-center justify-content-between py-3">
        <div>
          <div className="brand">SQL<span>Refine</span></div>
          <div className="small text-secondary">MySQL query optimizer & plan analyzer</div>
        </div>
        <span className="status-pill"><span /> Read-only analysis</span>
      </div>
    </header>
  )
}

