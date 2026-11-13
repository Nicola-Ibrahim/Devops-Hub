"use client";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { api, apiGeneration, isApiGenerationCurrent, isStaleRequest } from "@/lib/api/client";
import type { ConnectionDetails, Resource, ResourceOption } from "@/features/resources/types";
import { useWorkspace } from "@/features/workspace/session";
import { useResources } from "./use-resources";
type PendingRequest = {
    body: string;
    key: string;
};
type RevealedConnection = {
    resourceId: string;
    details: ConnectionDetails;
};
const optionKey = (option: ResourceOption) => `${option.template_id}:${option.version}:${option.target_id}:${option.size.id}`;
const formatDate = (value: string) => new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
const formatBytes = (value: number) => value >= 1024 ** 3 ? `${(value / 1024 ** 3).toFixed(1)} GB` : `${Math.round(value / 1024 ** 2)} MB`;
function extensionChoices(resource: Resource, options: ResourceOption[]) {
    const max = options.filter(option => option.template_id === resource.template_id && option.target_id === resource.target_id && option.size.id === resource.size_id).reduce((value, option) => Math.max(value, option.max_lifetime_seconds), 0);
    const created = Date.parse(resource.created_at);
    const expiry = Date.parse(resource.expires_at);
    if (!max || Number.isNaN(created) || Number.isNaN(expiry))
        return [];
    return [7200, 14400, 28800, 43200, 86400].filter(seconds => seconds <= max && created + seconds * 1000 > expiry && created + seconds * 1000 > Date.now());
}
export function ResourcesPage() {
    const { project } = useWorkspace();
    const { resources, options, operations, error, resourceError, catalogError, after, loading, refresh, loadMore, rememberOperation } = useResources();
    const [name, setName] = useState("");
    const [environment, setEnvironment] = useState("");
    const [optionValue, setOptionValue] = useState("");
    const [ttl, setTtl] = useState(3600);
    const [busy, setBusy] = useState(false);
    const [notice, setNotice] = useState("");
    const [actionError, setActionError] = useState("");
    const [pendingRequest, setPendingRequest] = useState<PendingRequest | null>(null);
    const [connection, setConnection] = useState<RevealedConnection | null>(null);
    const [renewing, setRenewing] = useState<Resource | null>(null);
    const [renewSeconds, setRenewSeconds] = useState(7200);
    const dialogRef = useRef<HTMLElement | null>(null);
    const returnFocus = useRef<HTMLElement | null>(null);
    const mounted = useRef(false);
    const selectedOption = useMemo(() => options.find(option => optionKey(option) === optionValue), [options, optionValue]);
    const showDialog = !!connection || !!renewing;
    useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
    useEffect(() => {
        if (!project) {
            setEnvironment("");
            return;
        }
        setEnvironment(current => project.environments.some(item => item.id === current) ? current : project.environments[0]?.id ?? "");
        const available = options.find(item => optionKey(item) === optionValue && item.requestable) ?? options.find(item => item.requestable);
        setOptionValue(available ? optionKey(available) : "");
        if (available)
            setTtl(current => Math.min(current, available.max_lifetime_seconds));
    }, [project, options]);
    useEffect(() => {
        if (!showDialog)
            return;
        if (!returnFocus.current)
            returnFocus.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
        const dialog = dialogRef.current;
        const focusable = () => [...(dialog?.querySelectorAll<HTMLElement>('a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])') ?? [])];
        focusable()[0]?.focus();
        const onKeyDown = (event: KeyboardEvent) => {
            if (event.key === "Escape") {
                event.preventDefault();
                setConnection(null);
                setRenewing(null);
                return;
            }
            if (event.key !== "Tab")
                return;
            const items = focusable();
            if (!items.length) {
                event.preventDefault();
                return;
            }
            if (event.shiftKey && document.activeElement === items[0]) {
                event.preventDefault();
                items.at(-1)?.focus();
            }
            else if (!event.shiftKey && document.activeElement === items.at(-1)) {
                event.preventDefault();
                items[0].focus();
            }
        };
        document.addEventListener("keydown", onKeyDown);
        return () => { document.removeEventListener("keydown", onKeyDown); returnFocus.current?.focus(); returnFocus.current = null; };
    }, [showDialog]);
    async function createResource(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        if (!project || !selectedOption?.requestable || !environment || !name.trim())
            return;
        const body = JSON.stringify({ project_id: project.project_id, environment_id: environment, display_name: name.trim(), template_id: selectedOption.template_id, version: selectedOption.version, target_id: selectedOption.target_id, size_id: selectedOption.size.id, ttl_seconds: Math.min(ttl, selectedOption.max_lifetime_seconds) });
        const pending = pendingRequest?.body === body ? pendingRequest : { body, key: crypto.randomUUID() };
        setPendingRequest(pending);
        setBusy(true);
        setNotice("");
        setActionError("");
        const generation = apiGeneration();
        const projectId = project.project_id;
        try {
            const accepted = await api<{
                resource_id: string;
                operation_id: string;
            }>("resources", { method: "POST", headers: { "Idempotency-Key": pending.key }, body });
            if (!mounted.current || !isApiGenerationCurrent(generation))
                return;
            rememberOperation(accepted.resource_id, accepted.operation_id);
            setPendingRequest(null);
            setName("");
            setNotice(`Request accepted. Operation ${accepted.operation_id} is being processed.`);
            await refresh();
            if (projectId !== project.project_id)
                return;
        }
        catch (cause) {
            if (mounted.current && !isStaleRequest(cause) && isApiGenerationCurrent(generation))
                setActionError(`${cause instanceof Error ? cause.message : "Request failed"}. Retry with the same request details to reuse its idempotency key.`);
        }
        finally {
            if (mounted.current && isApiGenerationCurrent(generation))
                setBusy(false);
        }
    }
    async function revealConnection(resource: Resource) {
        returnFocus.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
        if (resource.status !== "ready" || resource.desired_state === "deleted")
            return;
        const generation = apiGeneration();
        setBusy(true);
        setNotice("");
        setActionError("");
        setConnection(null);
        try {
            const details = await api<ConnectionDetails>(`resources/${resource.id}/connection`, { method: "POST", body: "{}" });
            if (mounted.current && isApiGenerationCurrent(generation))
                setConnection({ resourceId: resource.id, details });
        }
        catch (cause) {
            if (mounted.current && !isStaleRequest(cause) && isApiGenerationCurrent(generation))
                setActionError(cause instanceof Error ? cause.message : "Connection details could not be retrieved");
        }
        finally {
            if (mounted.current && isApiGenerationCurrent(generation))
                setBusy(false);
        }
    }
    async function renewResource(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        if (!renewing)
            return;
        const generation = apiGeneration();
        const resource = renewing;
        setActionError("");
        setNotice("");
        const expiresAt = new Date(Date.parse(resource.created_at) + renewSeconds * 1000).toISOString();
        setBusy(true);
        setNotice("");
        try {
            await api(`resources/${resource.id}/renew`, { method: "POST", body: JSON.stringify({ expected_revision: resource.revision, expires_at: expiresAt }) });
            if (!mounted.current || !isApiGenerationCurrent(generation))
                return;
            setRenewing(null);
            setNotice("Resource lease updated.");
            await refresh();
        }
        catch (cause) {
            if (mounted.current && !isStaleRequest(cause) && isApiGenerationCurrent(generation))
                setActionError(cause instanceof Error ? cause.message : "Lease update failed");
        }
        finally {
            if (mounted.current && isApiGenerationCurrent(generation))
                setBusy(false);
        }
    }
    async function deleteResource(resource: Resource) {
        if (!window.confirm(`Delete ${resource.display_name}? This permanently removes its database container, dedicated volume and stored data. This cannot be undone.`))
            return;
        const generation = apiGeneration();
        setBusy(true);
        setNotice("");
        setActionError("");
        try {
            await api(`resources/${resource.id}`, { method: "DELETE" });
            if (!mounted.current || !isApiGenerationCurrent(generation))
                return;
            setNotice(`Deletion requested for ${resource.display_name}. Cleanup status remains visible here.`);
            await refresh();
        }
        catch (cause) {
            if (mounted.current && !isStaleRequest(cause) && isApiGenerationCurrent(generation))
                setActionError(`${cause instanceof Error ? cause.message : "Deletion request failed"}. The resource remains listed so cleanup can be retried.`);
        }
        finally {
            if (mounted.current && isApiGenerationCurrent(generation))
                setBusy(false);
        }
    }
    return <div className="content-wrap">
    <header className="page-heading"><div><div className="eyebrow">DEVELOPER PLATFORM</div><h1>Your resources</h1><p>Approved development databases, operation status and lease expiry.</p></div><span className="environment-pill">{project?.configured ? "Project configured" : "Setup required"}</span></header>
    {actionError && <p role="alert" className="alert error">{actionError}<button onClick={() => setActionError("")} aria-label="Dismiss">×</button></p>}{notice && <p role="status" className="alert success">{notice}<button onClick={() => setNotice("")} aria-label="Dismiss">×</button></p>}
    <div className="dashboard-grid">
      <section className="panel request-panel"><div className="panel-heading"><div><div className="eyebrow">RESOURCE CATALOG</div><h2>Request a database</h2></div></div>
        {!project?.configured && <p className="notice-box">This project is not configured for self-service resources. Contact your platform administrator.</p>}
        {options.length > 0 && options.every(item => !item.requestable) && <p className="notice-box muted">Approved options are listed, but no verified database runtime is currently available.</p>}
        {catalogError && <p role="alert" className="failure-line">Catalog unavailable: {catalogError}</p>}
        <form className="request-form" onSubmit={createResource}>
          <label>Database option<select required value={optionValue} onChange={event => setOptionValue(event.target.value)} disabled={!options.some(item => item.requestable)}><option value="">Select an approved option</option>{options.map(item => <option key={optionKey(item)} value={optionKey(item)} disabled={!item.requestable}>{item.template_id} · PostgreSQL {item.version} · {item.size.id}{item.requestable ? "" : ` — ${item.unavailable_reason ?? "Not available"}`}</option>)}</select></label>
          {selectedOption && <div className="option-specs"><span><b>{selectedOption.size.cpu_millis / 1000}</b> vCPU</span><span><b>{formatBytes(selectedOption.size.memory_bytes)}</b> memory</span><span><b>{formatBytes(selectedOption.size.storage_bytes)}</b> storage</span></div>}
          <label>Resource name<input required maxLength={100} value={name} onChange={event => setName(event.target.value)} placeholder="e.g. checkout-feature-test"/></label>
          <label>Environment<select required value={environment} onChange={event => setEnvironment(event.target.value)} disabled={!project?.environments.length}><option value="">Choose an environment</option>{project?.environments.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
          <label>Lifetime<select value={ttl} onChange={event => setTtl(Number(event.target.value))} disabled={!selectedOption}><option value="">Choose a lifetime</option>{selectedOption && [...new Set([3600, 14400, 28800, 86400].filter(seconds => seconds <= selectedOption.max_lifetime_seconds).concat(selectedOption.max_lifetime_seconds))].sort((a, b) => a - b).map(seconds => <option key={seconds} value={seconds}>{seconds < 3600 ? `${seconds / 60} minutes` : seconds % 3600 === 0 ? `${seconds / 3600} hour${seconds === 3600 ? "" : "s"}` : `${Math.floor(seconds / 3600)}h ${Math.floor(seconds % 3600 / 60)}m`}</option>)}</select><span className="field-hint">Maximum: {selectedOption ? `${Math.floor(selectedOption.max_lifetime_seconds / 3600)} hours` : "—"}</span></label>
          <div className="form-footer"><span className="policy-note">Database and stored data are removed at expiry.</span><button className="primary-button" type="submit" disabled={busy || !project?.configured || !environment || !name.trim() || !selectedOption?.requestable}>{busy ? "Working…" : "Request database →"}</button></div>
        </form>
      </section>
      <section className="panel resources-panel"><div className="panel-heading resources-heading"><div><div className="eyebrow">PROJECT ENVIRONMENTS</div><h2>Active resources <span className="count">{resources.length}</span></h2></div><button className="refresh-button" onClick={() => void refresh()} aria-label="Refresh resources">↻</button></div>
        {resourceError && <p role="alert" className="failure-line">Resources unavailable: {resourceError} <button type="button" onClick={() => void refresh()}>Retry</button></p>}
        {loading && resources.length === 0 && <p role="status">Loading resources…</p>}
        {!loading && !resourceError && resources.length === 0 && <p className="empty-state">No resources yet. Requested resources will appear with their status and expiry.</p>}
        <div className="resource-list">{resources.map(resource => {
            const choices = extensionChoices(resource, options);
            const ready = resource.status === "ready" && resource.desired_state !== "deleted";
            return <article className="resource-card" key={resource.id}><div className="resource-card-top"><div className="db-icon">▤</div><div className="resource-title"><Link href={`/dashboard/resources/${resource.id}`}><strong>{resource.display_name}</strong></Link><span>{resource.template_id.replaceAll("_", " ")} · {resource.target_id} · {resource.size_id}</span></div><span className={`status status-${resource.status}`}><i />{resource.status.replaceAll("_", " ")}</span></div>
            <div className="resource-meta"><span><small>ENVIRONMENT</small><b>{project?.environments.find(item => item.id === resource.environment_id)?.name ?? "Environment"}</b></span><span><small>EXPIRES</small><b>{formatDate(resource.expires_at)}</b></span><span><small>RESOURCE ID</small><b className="mono">{resource.id.slice(0, 8)}</b></span></div>
            {operations[resource.id] && <div className={`operation-line operation-${operations[resource.id].status}`}>Operation {operations[resource.id].action} · {operations[resource.id].status}{operations[resource.id].error_code ? ` · ${operations[resource.id].error_code}` : ""} · attempt {operations[resource.id].attempts}</div>}
            {resource.failure_code && <div className="failure-line" role="status">Provisioning or cleanup needs attention · {resource.failure_code}. The resource remains tracked.</div>}
            {connection?.resourceId === resource.id && <div className="inline-connection">Connection is open in the secure dialog. <button onClick={() => void revealConnection(resource)}>Show again</button></div>}
            <div className="resource-actions"><button onClick={() => void revealConnection(resource)} disabled={!ready || busy}>⌁ <span>Connect</span></button><button onClick={() => { setRenewing(resource); setRenewSeconds(choices[0] ?? 0); }} disabled={!ready || busy || !choices.length}>◷ <span>Extend</span></button><button className="delete-action" onClick={() => void deleteResource(resource)} disabled={resource.status === "deleting" || busy}>⌫ <span>{resource.status === "deleting" ? "Deletion tracked" : resource.status === "cleanup_failed" ? "Retry cleanup" : "Delete"}</span></button></div>
          </article>;
        })}</div>{after && <button className="secondary-button" type="button" onClick={() => void loadMore()}>Load more resources</button>}{error && <p role="status">{error}</p>}
      </section>
    </div>
    {connection && <div className="modal-backdrop" role="presentation" onMouseDown={event => {
                if (event.target === event.currentTarget)
                    setConnection(null);
            }}><section ref={dialogRef} className="modal" role="dialog" aria-modal="true" aria-labelledby="connection-title" tabIndex={-1}><button className="modal-close" onClick={() => setConnection(null)} aria-label="Close">×</button><div className="eyebrow">SENSITIVE ACCESS</div><h2 id="connection-title">Database connection</h2><p>This connection string contains a password. It stays in page memory until this dialog closes.</p><div className="connection-facts"><span><small>HOST</small><b>{connection.details.host}</b></span><span><small>PORT</small><b>{connection.details.port}</b></span><span><small>DATABASE</small><b>{connection.details.database}</b></span><span><small>USER</small><b>{connection.details.user}</b></span></div><textarea readOnly value={connection.details.connection_string} aria-label="Database connection string" onFocus={event => event.currentTarget.select()}/><p>{connection.details.instructions}</p><div className="modal-footer"><span>Access is recorded for security.</span><button className="secondary-button" onClick={() => void navigator.clipboard.writeText(connection.details.connection_string).then(() => setNotice("Connection string copied. Handle it like a password."), () => setNotice("Clipboard access was blocked. Select and copy manually."))}>Copy connection</button><button className="primary-button" onClick={() => setConnection(null)}>Done</button></div></section></div>}
    {renewing && <div className="modal-backdrop"><section ref={dialogRef} className="modal" role="dialog" aria-modal="true" aria-labelledby="renew-title" tabIndex={-1}><button className="modal-close" onClick={() => setRenewing(null)} aria-label="Close">×</button><div className="eyebrow">RESOURCE LIFECYCLE</div><h2 id="renew-title">Extend lease</h2><p>Choose a total lease measured from database creation. It must remain within the catalog limit.</p><form onSubmit={renewResource}><label>Total lease<select value={renewSeconds} onChange={event => setRenewSeconds(Number(event.target.value))} disabled={!extensionChoices(renewing, options).length}>{extensionChoices(renewing, options).map(seconds => <option key={seconds} value={seconds}>{seconds / 3600} hours total</option>)}</select></label>{extensionChoices(renewing, options).length > 0 ? <p className="field-hint">New expiry: {formatDate(new Date(Date.parse(renewing.created_at) + renewSeconds * 1000).toISOString())}</p> : <p className="field-hint">This resource reached its maximum permitted lifetime.</p>}<div className="modal-footer"><button className="secondary-button" type="button" onClick={() => setRenewing(null)}>Cancel</button><button className="primary-button" type="submit" disabled={busy || !extensionChoices(renewing, options).includes(renewSeconds)}>{busy ? "Saving…" : "Update lease"}</button></div></form></section></div>}
  </div>;
}
