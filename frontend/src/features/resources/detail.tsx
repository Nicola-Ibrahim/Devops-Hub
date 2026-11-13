"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, apiGeneration, ApiError, isApiGenerationCurrent, isStaleRequest } from "@/lib/api/client";
import type { Resource } from "@/features/resources/types";
import { useWorkspace } from "@/features/workspace/session";
export function ResourceDetail({ id }: {
    id: string;
}) {
    const { project } = useWorkspace();
    const [data, setData] = useState<Resource | null>(null);
    const [error, setError] = useState("");
    const [loading, setLoading] = useState(true);
    const [attempt, setAttempt] = useState(0);
    const sequence = useRef(0);
    const load = useCallback(async (signal: AbortSignal) => {
        const currentRequest = ++sequence.current;
        const generation = apiGeneration();
        const current = () => !signal.aborted && sequence.current === currentRequest && isApiGenerationCurrent(generation);
        setData(null);
        setError("");
        setLoading(true);
        try {
            const result = await api<Resource>(`resources/${encodeURIComponent(id)}`, { signal });
            if (current())
                setData(result);
        }
        catch (cause) {
            if (current() && !isStaleRequest(cause))
                setError(cause instanceof ApiError && cause.status === 403 ? "Your account cannot access this resource in the current project." : cause instanceof ApiError && cause.status === 404 ? "This resource was not found in the current project." : cause instanceof Error ? cause.message : "Resource unavailable");
        }
        finally {
            if (current())
                setLoading(false);
        }
    }, [id, project?.project_id]);
    useEffect(() => { const controller = new AbortController(); void load(controller.signal); return () => { controller.abort(); sequence.current += 1; }; }, [load, attempt]);
    return <div className="content-wrap detail-content"><header className="page-heading"><div><div className="eyebrow">PROJECT WORKSPACE / RESOURCE</div><h1>{data?.display_name ?? "Resource details"}</h1><p>Project access follows the currently selected workspace.</p></div></header>
    {loading ? <p role="status">Loading resource…</p> : error ? <section className="panel"><p role="alert">{error}</p><button className="secondary-button" onClick={() => setAttempt(value => value + 1)}>Retry</button></section> : data && <section className="panel"><dl className="detail-facts">{Object.entries({ id: data.id, status: data.status, desired_state: data.desired_state, project_id: data.project_id, environment_id: data.environment_id, template_id: data.template_id, target_id: data.target_id, size_id: data.size_id, created_at: data.created_at, expires_at: data.expires_at, failure_code: data.failure_code }).filter(([, value]) => value !== undefined && value !== null).map(([key, value]) => <div key={key}><dt>{key.replaceAll("_", " ")}</dt><dd>{String(value)}</dd></div>)}</dl></section>}
  </div>;
}
