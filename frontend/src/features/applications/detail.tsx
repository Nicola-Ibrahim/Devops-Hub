"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, apiGeneration, ApiError, isApiGenerationCurrent, isStaleRequest } from "@/lib/api/client";
import type { AppDetails } from "@/features/applications/types";
import { useWorkspace } from "@/features/workspace/session";
export function ApplicationDetail({ id }: {
    id: string;
}) {
    const { project } = useWorkspace();
    const [data, setData] = useState<AppDetails | null>(null);
    const [error, setError] = useState("");
    const [attempt, setAttempt] = useState(0);
    const [loading, setLoading] = useState(true);
    const sequence = useRef(0);
    const load = useCallback(async (signal: AbortSignal) => {
        const request = ++sequence.current;
        const generation = apiGeneration();
        const current = () => !signal.aborted && sequence.current === request && isApiGenerationCurrent(generation);
        setData(null);
        setError("");
        setLoading(true);
        try {
            const result = await api<AppDetails>(`applications/${encodeURIComponent(id)}`, { signal });
            if (current())
                setData(result);
        }
        catch (cause) {
            if (current() && !isStaleRequest(cause))
                setError(cause instanceof ApiError && cause.status === 403 ? "Your account cannot access this application in the current project." : cause instanceof ApiError && cause.status === 404 ? "This application was not found in the current project." : cause instanceof Error ? cause.message : "Application unavailable");
        }
        finally {
            if (current())
                setLoading(false);
        }
    }, [id, project?.project_id]);
    useEffect(() => { const controller = new AbortController(); void load(controller.signal); return () => { controller.abort(); sequence.current += 1; }; }, [load, attempt]);
    return <div className="content-wrap detail-content"><header className="page-heading"><div><div className="eyebrow">PROJECT WORKSPACE / APPLICATION</div><h1>{data?.application.name ?? "Application details"}</h1><p>Repository creation and delivery operations run asynchronously.</p></div></header>{loading ? <p role="status">Loading application…</p> : error ? <section className="panel"><p role="alert">{error}</p><button className="secondary-button" onClick={() => setAttempt(value => value + 1)}>Retry</button></section> : data && <section className="panel"><p>Status: <strong>{data.application.status}</strong></p><p>Template: {data.application.template_id} · v{data.application.template_version}</p>{data.application.repository_url && <p>Repository: <a href={data.application.repository_url}>{data.application.repository_url}</a></p>}<div className="delivery-steps">{data.steps.map(step => <div className="delivery-step" key={step.id}><b>{step.kind.replaceAll("_", " ")}</b><span>{step.status}</span><small>{step.error_code ?? `Attempts: ${step.attempts}`}</small></div>)}</div></section>}</div>;
}
