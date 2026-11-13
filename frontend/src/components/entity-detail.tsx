"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

type RecordData = Record<string, unknown>;

export default function EntityDetail({ kind, id }: { kind: "resources" | "applications"; id: string }) {
  const [data, setData] = useState<RecordData | null>(null);
  const [error, setError] = useState("");
  const [anonymous, setAnonymous] = useState(false);
  const [loading, setLoading] = useState(true);
  const load = useCallback(async (signal: AbortSignal) => {
    setLoading(true); setError(""); setAnonymous(false);
    try {
      const response = await fetch(`/api/v1/${kind}/${encodeURIComponent(id)}`, { credentials: "same-origin", cache: "no-store", signal });
      if (!response.ok) { setAnonymous(response.status === 401); throw new Error(response.status === 401 ? "Sign in to view this item." : response.status === 403 ? "Your account cannot access this item in the current project." : response.status === 404 ? "This item was not found in the current project." : "Details are unavailable. Try again."); }
      const value = await response.json();
      if (!signal.aborted) setData(value);
    } catch (cause) { if (!signal.aborted) { setData(null); setError(cause instanceof Error ? cause.message : "Details unavailable"); } }
    finally { if (!signal.aborted) setLoading(false); }
  }, [kind, id]);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => { const controller = new AbortController(); void load(controller.signal); return () => controller.abort(); }, [load, attempt]);
  const entity = (kind === "applications" ? data?.application : data) as RecordData | null;
  const steps = (Array.isArray(data?.steps) ? data.steps : []) as RecordData[];
  return <main className="detail-page"><header className="landing-nav"><Link href="/" className="brand"><span className="brand-mark">d.</span>devopshub</Link><Link className="secondary-button" href={`/dashboard/${kind}`}>← Back to {kind}</Link></header><div className="detail-content"><span className="eyebrow">PROJECT WORKSPACE / {kind.toUpperCase()}</span><h1>{String(entity?.display_name ?? entity?.name ?? "Details")}</h1><p className="identity-muted">Access follows your currently selected project. Change projects in the workspace if necessary.</p>{loading ? <p role="status">Loading details…</p> : error ? <section className="panel"><p role="alert">{error}</p>{anonymous ? <Link className="primary-button" href={`/login?next=${encodeURIComponent(`/dashboard/${kind}/${id}`)}`}>Sign in</Link> : <button className="secondary-button" onClick={() => setAttempt(value => value + 1)}>Retry</button>}</section> : entity && <section className="panel"><dl className="detail-facts">{["id", "status", "desired_state", "project_id", "environment_id", "template_id", "target_id", "size_id", "created_at", "expires_at", "failure_code"].filter(key => entity[key] !== undefined && entity[key] !== null).map(key => <div key={key}><dt>{key.replaceAll("_", " ")}</dt><dd>{String(entity[key])}</dd></div>)}</dl>{steps.length > 0 && <><h2>Delivery progress</h2><div className="delivery-steps">{steps.map(step => <div className="delivery-step" key={String(step.id)}><span className={`step-dot step-${step.status}`} /><b>{String(step.kind).replaceAll("_", " ")}</b><span>{String(step.status)}</span><small>Attempts: {String(step.attempts)}{step.error_code ? ` · ${step.error_code}` : ""}</small></div>)}</div></>}<p className="field-hint">Use the {kind} workspace for authorized lifecycle actions and sensitive connection retrieval.</p><Link className="primary-button" href={`/dashboard/${kind}`}>Manage {kind} →</Link></section>}</div></main>;
}
