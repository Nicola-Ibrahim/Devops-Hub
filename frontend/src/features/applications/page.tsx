"use client";
import Link from "next/link";
import { useApplications } from "./use-applications";
export function ApplicationsPage() {
    const state = useApplications();
    const { project } = state;
    return <div className="content-wrap">
    <header className="page-heading"><div><div className="eyebrow">DEVELOPER PLATFORM</div><h1>Applications</h1><p>Approved templates, local previews and delivery progress.</p></div><span className="environment-pill">{project?.configured ? "Project configured" : "Setup required"}</span></header>
    {state.error && <p role="alert" className="alert error">{state.error} <button onClick={() => void state.refresh()}>Retry</button></p>}{state.catalogError && <p role="alert" className="alert error">Database catalog unavailable: {state.catalogError}. Database attachment is unavailable.</p>}{state.notice && <p role="status" className="alert success">{state.notice}</p>}
    <section className="panel applications-panel">
      <div className="panel-heading"><div><div className="eyebrow">APP STARTER</div><h2>Applications <span className="count">{state.applications.length}</span></h2></div></div>
      <form className="application-create" onSubmit={event => void state.createApplication(event)}>
        <label>Approved template<select required value={state.template} onChange={event => state.setTemplate(event.target.value)}><option value="">Select a template</option>{state.templates.map(item => <option key={`${item.id}@${item.version}`} value={`${item.id}@${item.version}`}>{item.name} · {item.language} · v{item.version}</option>)}</select></label>
        <label>Environment<select required value={state.environment} onChange={event => state.setEnvironment(event.target.value)}><option value="">Choose an environment</option>{project?.environments.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        <label>Application name<input required maxLength={64} value={state.applicationName} onChange={event => state.setApplicationName(event.target.value)} placeholder="e.g. checkout-service"/></label>
        <button className="primary-button" disabled={state.busyId !== "" || !project?.configured || !state.templates.length || !project.environments.length}>{state.busyId === "application" ? "Working…" : "Create application →"}</button>
      </form>
      {state.loading ? <p role="status">Loading applications…</p> : state.applications.length === 0 ? <p className="applications-empty">Choose an approved template to start a project. Repository creation runs asynchronously.</p> : <div className="application-list">{state.applications.map(({ application, steps }) => <article className="application-card" key={application.id}>
        <div className="application-heading"><div><Link href={`/dashboard/applications/${application.id}`}><strong>{application.name}</strong></Link><small>{application.template_id} · v{application.template_version} · {application.repository_url ?? "Repository pending"}</small></div><span className={`status status-${application.status}`}><i />{application.status}</span></div>
        <div className="delivery-steps">{steps.map(step => <div className="delivery-step" key={step.id}><span className={`step-dot step-${step.status}`}/><span>{step.kind.replaceAll("_", " ")}</span><b>{step.status}</b><small>{step.attempts ? `attempt ${step.attempts}` : "queued"}{step.error_code ? ` · ${step.error_code}` : ""}</small>{step.status === "failed" && <button className="secondary-button" onClick={() => void state.retryStep(application, step)} disabled={state.busyId !== ""}>Retry step</button>}</div>)}</div>
      </article>)}</div>}
    </section>
    <section className="panel local-preview-panel">
      <div className="panel-heading"><div><div className="eyebrow">APPLICATION DELIVERY</div><h2>Register a local preview</h2></div><span className="catalog-icon">⌁</span></div>
      <p className="preview-intro">Attach an approved local database and deploy an immutable image digest when supported. Preview addresses are for this machine only.</p>
      <form className="local-preview-form" onSubmit={event => void state.registerPreview(event)}>
        <label>Preview name<input required maxLength={64} value={state.previewName} onChange={event => state.setPreviewName(event.target.value)} placeholder="e.g. checkout-preview"/></label>
        <label>Environment<select required value={state.previewEnvironment} onChange={event => state.setPreviewEnvironment(event.target.value)}><option value="">Choose an environment</option>{project?.environments.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        <label>Lease<select value={state.previewTtl} onChange={event => state.setPreviewTtl(Number(event.target.value))}><option value={3600}>1 hour</option><option value={14400}>4 hours</option><option value={86400}>24 hours</option></select></label>
        <button className="primary-button" disabled={state.busyId !== "" || !project?.configured || !project.environments.length}>{state.busyId === "preview" ? "Registering…" : "Register local image →"}</button>
      </form>
      {state.loading ? <p role="status">Loading preview status…</p> : state.previews.length === 0 ? <p className="applications-empty">Registered local previews appear here with deployment history.</p> : <div className="application-list">{state.previews.map(preview => {
                const deployment = preview.deployments.at(-1);
                const resource = state.resources.find(item => item.id === preview.application.resource_id);
                const deployed = deployment?.status === "succeeded" || deployment?.status === "ready";
                const attachment = [...(preview.steps ?? [])].reverse().find(step => step.kind === "resource");
                const pending = attachment?.status === "pending" || attachment?.status === "running";
                const waiting = pending || !!preview.application.resource_id && resource?.status !== "ready";
                return <article className="application-card" key={preview.application.id}>
          <div className="application-heading"><div><Link href={`/dashboard/applications/${preview.application.id}`}><strong>{preview.application.name}</strong></Link><small>{deployment?.image_digest ?? "Image digest required at deploy"} · {preview.application.template_id}</small></div><span className={`status status-${deployed ? "ready" : deployment?.status ?? "pending"}`}><i />{deployed ? "deployed" : deployment?.status ?? "registered"}</span></div>
          {state.historyErrors[preview.application.id] && <p className="failure-line" role="alert">Deployment history unavailable: {state.historyErrors[preview.application.id]} <button onClick={() => void state.refreshPreview(preview)}>Retry history</button></p>}
          <div className="preview-meta">{preview.application.expires_at && <span><small>EXPIRES</small><b>{new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(preview.application.expires_at))}</b></span>}<span><small>DATABASE</small><b>{!preview.application.resource_id ? "Not attached" : resource?.status ?? "Attachment pending"}</b></span></div>
          {preview.steps?.some(step => step.status === "failed") && <p className="failure-line" role="status">Delivery failed · {preview.steps.find(step => step.status === "failed")?.error_code ?? "check delivery status"}.</p>}
          {deployed && deployment?.url && state.deploymentUrlIsLocal(deployment.url) && <div className="preview-url"><strong>Local preview URL</strong><a href={deployment.url} target="_blank" rel="noreferrer">{deployment.url}</a><small>Loopback access on this machine only.</small></div>}
          {deployed && deployment?.url && !state.deploymentUrlIsLocal(deployment.url) && <p className="failure-line" role="status">Deployment succeeded, but the returned non-loopback address is hidden.</p>}
          <div className="preview-actions">{!preview.application.resource_id && <button className="secondary-button" onClick={() => void state.attachDatabase(preview)} disabled={state.busyId !== "" || pending || !state.options.some(option => option.target_id === "local" && option.requestable)}>{attachment?.status === "failed" ? "Retry database attachment" : "Attach approved database"}</button>}
            {(preview.application.resource_id || attachment) && <span className="field-hint">Database step: {pending ? "pending" : resource?.status ?? attachment?.status ?? "pending"}{waiting ? " — deployment waits for ready" : attachment?.status === "failed" ? " — attachment failed; deploy without database or retry" : " — ready"}</span>}
            <label className="preview-digest-field">Image digest for this deploy<input value={state.digests[preview.application.id] ?? ""} onChange={event => state.setDigests(current => ({ ...current, [preview.application.id]: event.target.value }))} placeholder="repo/image@sha256:… or sha256:<64 lowercase hex>" autoComplete="off" spellCheck={false}/><small>Immutable registry digest or configured local Docker image ID. Mutable tags are rejected.</small></label>
            <button className="primary-button" onClick={() => void state.deploy(preview)} disabled={state.busyId !== "" || deployed || waiting || !state.digests[preview.application.id]?.trim()}>{state.busyId === preview.application.id ? "Working…" : deployed ? "Deployment complete" : deployment?.status === "failed" ? "Retry deployment" : attachment?.status === "failed" ? "Deploy without database" : "Deploy locally"}</button>
          </div>
        </article>;
            })}</div>}
      {!state.options.some(option => option.requestable && option.target_id === "local") && <p className="field-hint">No approved local PostgreSQL option is currently available. Deployment can continue without a database.</p>}
    </section>
  </div>;
}
