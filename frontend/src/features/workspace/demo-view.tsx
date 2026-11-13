"use client";
export default function GuestDashboard({ onSignIn }: {
    onSignIn: () => void;
}) {
    return <main className="shell">
    <aside className="sidebar">
      <div className="brand"><span className="brand-mark">D</span><span>devops<span className="brand-light">hub</span></span></div>
      <div className="workspace-label">EXPLORE THE PLATFORM</div>
      <nav className="nav" aria-label="Guest navigation">
        <a className="nav-item active" href="#guest-resources">▦ Resources</a>
        <a className="nav-item" href="#guest-workflow">◇ How it works</a>
      </nav>
      <div className="sidebar-bottom"><span className="avatar">G</span><div className="user-copy"><strong>Guest visitor</strong><span>Read-only preview</span></div></div>
    </aside>
    <section className="main-content">
      <header className="topbar"><div className="breadcrumb">Explore <span>/</span> Developer platform</div><button className="secondary-button" onClick={onSignIn}>Sign in</button></header>
      <div className="content-wrap">
        <div className="page-heading"><div><div className="eyebrow">DEVELOPER PLATFORM</div><h1>Your development workspace.</h1><p>Explore temporary databases and the developer resource lifecycle.</p></div><span className="environment-pill">Guest preview</span></div>
        <div className="alert success" role="note"><span>◇</span><p>This preview uses illustrative data. Sign in with a company account to access projects and manage real resources.</p></div>
        <section className="panel" id="guest-resources" aria-labelledby="guest-resources-title">
          <div className="panel-heading"><h2 id="guest-resources-title">Resource catalog</h2><span>Example resource</span></div>
          <article className="resource-card">
            <div className="resource-card-top"><div className="db-icon">▤</div><div className="resource-title"><strong>PostgreSQL development database</strong><span>Isolated database · Temporary lease · Local Docker</span></div><span className="status">Preview</span></div>
            <p>Request an approved database for a feature branch, retrieve its connection details securely, and manage its expiry.</p>
            <div className="resource-actions"><button disabled title="Sign in to request a real database">Request database</button><button disabled title="Sign in to retrieve authorized credentials">Connect</button><button disabled title="Sign in to manage a resource lease">Extend lease</button></div>
          </article>
        </section>
        <section className="panel" id="guest-workflow" aria-labelledby="guest-workflow-title">
          <div className="panel-heading"><h2 id="guest-workflow-title">From request to cleanup</h2></div>
          <ol><li>Choose your project and an approved resource option.</li><li>Follow provisioning progress until the database is ready.</li><li>Retrieve connection details and develop your feature.</li><li>Extend the lease within policy, or delete the database when finished.</li></ol>
          <p>Access is limited by project permissions. Resource requests and sensitive actions are recorded.</p>
          <button className="primary-button" onClick={onSignIn}>Sign in to your workspace →</button>
        </section>
      </div>
    </section>
  </main>;
}
