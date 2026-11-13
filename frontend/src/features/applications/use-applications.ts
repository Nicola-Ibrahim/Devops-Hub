"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, apiGeneration, isApiGenerationCurrent, isStaleRequest } from "@/lib/api/client";
import type { App, AppDetails, AppTemplate, DeliveryStep, LocalPreview, PreviewDeployment } from "@/features/applications/types";
import type { Resource, ResourceOption } from "@/features/resources/types";
import { useWorkspace } from "@/features/workspace/session";
type Pending = {
    key: string;
    body: string;
};
function loopback(value: string) {
    try {
        const url = new URL(value);
        return ["http:", "https:"].includes(url.protocol) && !url.username && !url.password && ["localhost", "127.0.0.1", "[::1]", "::1"].includes(url.hostname);
    }
    catch {
        return false;
    }
}
export function useApplications() {
    const { project } = useWorkspace();
    const [templates, setTemplates] = useState<AppTemplate[]>([]);
    const [applications, setApplications] = useState<AppDetails[]>([]);
    const [previews, setPreviews] = useState<LocalPreview[]>([]);
    const [historyErrors, setHistoryErrors] = useState<Record<string, string>>({});
    const [resources, setResources] = useState<Resource[]>([]);
    const [options, setOptions] = useState<ResourceOption[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");
    const [catalogError, setCatalogError] = useState("");
    const [notice, setNotice] = useState("");
    const [busyId, setBusyId] = useState("");
    const [applicationName, setApplicationName] = useState("");
    const [template, setTemplate] = useState("");
    const [environment, setEnvironment] = useState("");
    const [previewName, setPreviewName] = useState("");
    const [previewEnvironment, setPreviewEnvironment] = useState("");
    const [previewTtl, setPreviewTtl] = useState(3600);
    const [digests, setDigests] = useState<Record<string, string>>({});
    const [pendingApplication, setPendingApplication] = useState<Pending | null>(null);
    const [pendingPreview, setPendingPreview] = useState<Pending | null>(null);
    const mutationKeys = useRef<Record<string, string>>({});
    const attachmentRequests = useRef<Record<string, Pending>>({});
    const active = useRef(false);
    const sequence = useRef(0);
    const requestController = useRef<AbortController | null>(null);
    const current = (request: number, generation: number) => active.current && request === sequence.current && isApiGenerationCurrent(generation);
    const refresh = useCallback(async () => {
        requestController.current?.abort();
        const controller = new AbortController();
        requestController.current = controller;
        const signal = controller.signal;
        const request = ++sequence.current;
        const generation = apiGeneration();
        const valid = () => current(request, generation);
        if (!project) {
            setTemplates([]);
            setApplications([]);
            setPreviews([]);
            setResources([]);
            setOptions([]);
            setLoading(false);
            return;
        }
        setLoading(true);
        try {
            const [catalog, rows, catalogOptions] = await Promise.all([
                api<AppTemplate[]>("templates", { signal }),
                api<App[]>("applications", { signal }),
                api<{
                    templates: ResourceOption[];
                }>("catalog", { signal }).then(value => ({ ...value, error: "" }), cause => { if (isStaleRequest(cause))
                    throw cause; return { templates: [] as ResourceOption[], error: cause instanceof Error ? cause.message : "Database catalog unavailable" }; }),
            ]);
            if (!valid())
                return;
            const details = await Promise.all(rows.map(item => api<AppDetails>(`applications/${item.id}`, { signal })));
            if (!valid())
                return;
            const histories = await Promise.all(rows.map(async (item) => {
                try {
                    return { id: item.id, items: await api<PreviewDeployment[]>(`applications/${item.id}/deployments`, { signal }), error: "" };
                }
                catch (cause) {
                    if (isStaleRequest(cause))
                        throw cause;
                    return { id: item.id, items: [] as PreviewDeployment[], error: cause instanceof Error ? cause.message : "Could not load deployment history" };
                }
            }));
            if (!valid())
                return;
            const historyById = new Map(histories.map(item => [item.id, item.items.filter(deploy => deploy.target_id === "local")]));
            setTemplates(catalog);
            setApplications(details.filter(item => item.application.template_id !== "local-image"));
            setPreviews(details.map(item => ({ application: item.application, steps: item.steps, deployments: historyById.get(item.application.id) ?? [] })));
            setHistoryErrors(Object.fromEntries(histories.filter(item => item.error).map(item => [item.id, item.error])));
            const resourceRows: Resource[] = [];
            let cursor: string | null = null;
            do {
                const query = new URLSearchParams({ limit: "100" });
                if (cursor)
                    query.set("after", cursor);
                const page = await api<{
                    items: Resource[];
                    next_after?: string | null;
                }>(`projects/${project.project_id}/resources?${query}`, { signal });
                resourceRows.push(...page.items);
                cursor = page.next_after ?? null;
            } while (cursor);
            if (!valid())
                return;
            setResources(resourceRows);
            setOptions(catalogOptions.templates ?? []);
            setCatalogError(catalogOptions.error);
            setError("");
            if (!template && catalog.length)
                setTemplate(`${catalog[0].id}@${catalog[0].version}`);
        }
        catch (cause) {
            if (valid() && !isStaleRequest(cause))
                setError(cause instanceof Error ? cause.message : "Applications are unavailable");
        }
        finally {
            if (valid())
                setLoading(false);
        }
    }, [project, template]);
    useEffect(() => {
        active.current = true;
        void refresh();
        if (!project)
            return () => { active.current = false; sequence.current += 1; requestController.current?.abort(); };
        const timer = window.setInterval(() => void refresh(), 5000);
        return () => { active.current = false; sequence.current += 1; requestController.current?.abort(); window.clearInterval(timer); };
    }, [refresh, project]);
    const refreshPreview = useCallback(async (preview: LocalPreview) => {
        const generation = apiGeneration();
        const projectId = project?.project_id;
        if (!projectId)
            return;
        try {
            const [details, history] = await Promise.all([api<AppDetails>(`applications/${preview.application.id}`), api<PreviewDeployment[]>(`applications/${preview.application.id}/deployments`)]);
            if (!isApiGenerationCurrent(generation))
                return;
            setHistoryErrors(current => { const next = { ...current }; delete next[preview.application.id]; return next; });
            setPreviews(current => current.map(item => item.application.id === preview.application.id ? { application: details.application, steps: details.steps, deployments: history.filter(value => value.target_id === "local") } : item));
        }
        catch (cause) {
            if (!isStaleRequest(cause) && isApiGenerationCurrent(generation))
                setHistoryErrors(current => ({ ...current, [preview.application.id]: cause instanceof Error ? cause.message : "Could not load deployment history" }));
        }
    }, [project]);
    async function createApplication(event: React.FormEvent) {
        event.preventDefault();
        if (!project || !applicationName.trim() || !template || !environment)
            return;
        const [id, version] = template.split("@");
        const body = JSON.stringify({ name: applicationName.trim(), environment_id: environment, template_id: id, template_version: version });
        const pending = pendingApplication?.body === body ? pendingApplication : { key: crypto.randomUUID(), body };
        setPendingApplication(pending);
        const generation = apiGeneration();
        setBusyId("application");
        setNotice("");
        setError("");
        try {
            const accepted = await api<{
                application: App;
            }>("applications", { method: "POST", headers: { "Idempotency-Key": pending.key }, body });
            if (!isApiGenerationCurrent(generation))
                return;
            setPendingApplication(null);
            setApplicationName("");
            setNotice(`Application ${accepted.application.name} is queued. Repository creation progress will appear here.`);
            await refresh();
        }
        catch (cause) {
            if (!isStaleRequest(cause) && isApiGenerationCurrent(generation))
                setError(`${cause instanceof Error ? cause.message : "Application request failed"}. Retry with the same form values to reuse the request key.`);
        }
        finally {
            if (isApiGenerationCurrent(generation))
                setBusyId("");
        }
    }
    async function retryStep(application: App, step: DeliveryStep) {
        if (step.status !== "failed")
            return;
        const generation = apiGeneration();
        setBusyId(application.id);
        setNotice("");
        setError("");
        try {
            await api<DeliveryStep>(`applications/${application.id}/steps/${step.id}/retry`, { method: "POST" });
            if (!isApiGenerationCurrent(generation))
                return;
            setNotice(`Retry requested for ${step.kind.replaceAll("_", " ")}.`);
            await refresh();
        }
        catch (cause) {
            if (!isStaleRequest(cause) && isApiGenerationCurrent(generation))
                setError(cause instanceof Error ? cause.message : "Could not retry delivery step");
        }
        finally {
            if (isApiGenerationCurrent(generation))
                setBusyId("");
        }
    }
    async function registerPreview(event: React.FormEvent) {
        event.preventDefault();
        if (!project || !previewName.trim() || !previewEnvironment)
            return;
        const body = JSON.stringify({ name: previewName.trim(), environment_id: previewEnvironment, ttl_seconds: previewTtl });
        const pending = pendingPreview?.body === body ? pendingPreview : { key: crypto.randomUUID(), body };
        setPendingPreview(pending);
        const generation = apiGeneration();
        setBusyId("preview");
        setNotice("");
        setError("");
        try {
            const accepted = await api<{
                application: App;
            }>("applications/local-preview", { method: "POST", headers: { "Idempotency-Key": pending.key }, body });
            if (!isApiGenerationCurrent(generation))
                return;
            setPreviews(current => [{ application: accepted.application, deployments: [] }, ...current.filter(item => item.application.id !== accepted.application.id)]);
            setPendingPreview(null);
            setPreviewName("");
            setNotice("Local preview registered. Attach a database if needed, then deploy when ready.");
        }
        catch (cause) {
            if (!isStaleRequest(cause) && isApiGenerationCurrent(generation))
                setError(`${cause instanceof Error ? cause.message : "Preview registration failed"}. Retry to reuse the request key.`);
        }
        finally {
            if (isApiGenerationCurrent(generation))
                setBusyId("");
        }
    }
    function mutationKey(action: string, id: string, body: string) { const identity = `${action}:${id}:${body}`; return mutationKeys.current[identity] ?? (mutationKeys.current[identity] = crypto.randomUUID()); }
    async function attachDatabase(preview: LocalPreview) {
        const option = options.find(item => item.target_id === "local" && item.requestable);
        if (!project || !option) {
            setError("No approved local PostgreSQL option is available. You can deploy without a database.");
            return;
        }
        const remaining = preview.application.expires_at ? Math.floor((Date.parse(preview.application.expires_at) - Date.now()) / 1000) - 10 : Math.min(3600, option.max_lifetime_seconds);
        if (remaining < 60) {
            setError("This preview has less than 70 seconds remaining. Register a new preview or deploy without a database.");
            return;
        }
        const body = JSON.stringify({ template_id: option.template_id, version: option.version, target_id: "local", size_id: option.size.id, ttl_seconds: Math.min(remaining, option.max_lifetime_seconds) });
        const pending = attachmentRequests.current[preview.application.id] ?? { body, key: mutationKey("attach", preview.application.id, body) };
        attachmentRequests.current[preview.application.id] = pending;
        const generation = apiGeneration();
        setBusyId(preview.application.id);
        setError("");
        setNotice("");
        try {
            const step = await api<DeliveryStep>(`applications/${preview.application.id}/resources`, { method: "POST", headers: { "Idempotency-Key": pending.key }, body: pending.body });
            if (!isApiGenerationCurrent(generation))
                return;
            setPreviews(current => current.map(item => item.application.id === preview.application.id ? { ...item, steps: [...(item.steps ?? []).filter(existing => existing.id !== step.id), step] } : item));
            delete attachmentRequests.current[preview.application.id];
            delete mutationKeys.current[`attach:${preview.application.id}:${body}`];
            await refreshPreview(preview);
            setNotice("Database attachment requested. Deployment unlocks when the resource is ready.");
        }
        catch (cause) {
            if (!isStaleRequest(cause) && isApiGenerationCurrent(generation))
                setError(cause instanceof Error ? cause.message : "Database attachment failed");
        }
        finally {
            if (isApiGenerationCurrent(generation))
                setBusyId("");
        }
    }
    async function deploy(preview: LocalPreview) {
        const digest = digests[preview.application.id]?.trim();
        if (!digest) {
            setError("Enter an immutable image digest before deploying.");
            return;
        }
        const attached = resources.find(item => item.id === preview.application.resource_id);
        const attachment = [...(preview.steps ?? [])].reverse().find(step => step.kind === "resource");
        if (attachment && ["pending", "running"].includes(attachment.status))
            return;
        if (preview.application.resource_id && attached?.status !== "ready")
            return;
        const body = JSON.stringify({ image_digest: digest, target_id: "local" });
        const key = mutationKey("deploy", preview.application.id, body);
        const generation = apiGeneration();
        setBusyId(preview.application.id);
        setError("");
        setNotice("");
        try {
            await api<PreviewDeployment>(`applications/${preview.application.id}/deployments`, { method: "POST", headers: { "Idempotency-Key": key }, body });
            if (!isApiGenerationCurrent(generation))
                return;
            delete mutationKeys.current[`deploy:${preview.application.id}:${body}`];
            await refreshPreview(preview);
            setNotice("Local deployment queued. Status will update automatically.");
        }
        catch (cause) {
            if (!isStaleRequest(cause) && isApiGenerationCurrent(generation))
                setError(cause instanceof Error ? cause.message : "Deployment failed. Retry is available.");
        }
        finally {
            if (isApiGenerationCurrent(generation))
                setBusyId("");
        }
    }
    const deploymentUrlIsLocal = loopback;
    return { project, templates, applications, previews, resources, options, historyErrors, loading, error, catalogError, notice, busyId, applicationName, setApplicationName, template, setTemplate, environment, setEnvironment, previewName, setPreviewName, previewEnvironment, setPreviewEnvironment, previewTtl, setPreviewTtl, digests, setDigests, refresh, refreshPreview, createApplication, retryStep, registerPreview, attachDatabase, deploy, deploymentUrlIsLocal };
}
