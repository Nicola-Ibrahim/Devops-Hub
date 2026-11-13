"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, apiGeneration, isApiGenerationCurrent, isStaleRequest } from "@/lib/api/client";
import type { Activity } from "@/features/activity/types";
import type { Operation, Resource, ResourceOption } from "@/features/resources/types";
import type { Page } from "@/lib/api/pagination";
import { useWorkspace } from "@/features/workspace/session";
export function useResources() {
    const { project } = useWorkspace();
    const [resources, setResources] = useState<Resource[]>([]);
    const [options, setOptions] = useState<ResourceOption[]>([]);
    const [operations, setOperations] = useState<Record<string, Operation>>({});
    const [operationIds, setOperationIds] = useState<Record<string, string>>({});
    const [after, setAfter] = useState<string | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");
    const [resourceError, setResourceError] = useState("");
    const [catalogError, setCatalogError] = useState("");
    const cursors = useRef<string[]>([]);
    const mounted = useRef(false);
    const sequence = useRef(0);
    const requestController = useRef<AbortController | null>(null);
    const refresh = useCallback(async () => {
        requestController.current?.abort();
        const controller = new AbortController();
        requestController.current = controller;
        const signal = controller.signal;
        const request = ++sequence.current;
        const generation = apiGeneration();
        const current = () => mounted.current && request === sequence.current && isApiGenerationCurrent(generation);
        if (!project) {
            setResources([]);
            setOptions([]);
            setOperations({});
            setAfter(null);
            setResourceError("");
            setCatalogError("");
            cursors.current = [];
            setLoading(false);
            return;
        }
        setLoading(true);
        const projectId = project.project_id;
        const queryCursors: (string | null)[] = [null, ...cursors.current];
        const [catalogResult, activityResult, resourceResult] = await Promise.allSettled([
            api<{
                templates: ResourceOption[];
            }>("catalog", { signal }),
            api<{
                items: Activity[];
            }>(`projects/${projectId}/activity`, { signal }),
            (async () => {
                const pages: Page<Resource>[] = [];
                for (let index = 0; index < queryCursors.length; index += 1) {
                    const query = new URLSearchParams({ limit: "25" });
                    const cursor = pages.at(-1)?.next_after ?? null;
                    if (cursor)
                        query.set("after", cursor);
                    const page = await api<Page<Resource>>(`projects/${projectId}/resources?${query}`, { signal });
                    pages.push(page);
                    if (!page.next_after)
                        break;
                }
                return pages;
            })(),
        ]);
        if (!current())
            return;
        if (catalogResult.status === "fulfilled") {
            setOptions(catalogResult.value.templates ?? []);
            setCatalogError("");
        }
        else if (!isStaleRequest(catalogResult.reason))
            setCatalogError(catalogResult.reason instanceof Error ? catalogResult.reason.message : "Could not load resource catalog");
        if (resourceResult.status === "rejected") {
            if (!isStaleRequest(resourceResult.reason)) {
                setResourceError(resourceResult.reason instanceof Error ? resourceResult.reason.message : "Could not load resources");
                setError(resourceResult.reason instanceof Error ? resourceResult.reason.message : "Could not load resources");
            }
            setLoading(false);
            return;
        }
        const pages = resourceResult.value;
        const rows = pages.flatMap(page => page.items);
        const loadedCursors = pages.slice(0, -1).map(page => page.next_after).filter((cursor): cursor is string => !!cursor);
        cursors.current = loadedCursors;
        setResources(rows.filter((item, index) => rows.findIndex(candidate => candidate.id === item.id) === index));
        setAfter(pages.at(-1)?.next_after ?? null);
        setResourceError("");
        setError("");
        const ids = new Map(Object.entries(operationIds));
        if (activityResult.status === "fulfilled") {
            for (const event of activityResult.value.items.slice(0, 10)) {
                if (event.resource_id && event.operation_id && !ids.has(event.resource_id))
                    ids.set(event.resource_id, event.operation_id);
            }
        }
        const operationsResult = await Promise.allSettled([...ids].map(async ([resourceId, id]) => [resourceId, await api<Operation>(`operations/${id}`, { signal })] as const));
        if (!current())
            return;
        setOperations(Object.fromEntries(operationsResult.filter((result): result is PromiseFulfilledResult<readonly [
            string,
            Operation
        ]> => result.status === "fulfilled").map(result => result.value)));
        setLoading(false);
    }, [project, operationIds]);
    useEffect(() => {
        mounted.current = true;
        void refresh();
        const timer = window.setInterval(() => void refresh(), 5000);
        return () => { mounted.current = false; sequence.current += 1; requestController.current?.abort(); window.clearInterval(timer); };
    }, [refresh, project]);
    const loadMore = useCallback(async () => {
        if (!project || !after)
            return;
        const cursor = after;
        const generation = apiGeneration();
        try {
            const query = new URLSearchParams({ limit: "25", after: cursor });
            const page = await api<Page<Resource>>(`projects/${project.project_id}/resources?${query}`);
            if (!mounted.current || !isApiGenerationCurrent(generation))
                return;
            cursors.current = [...cursors.current, cursor];
            setResources(current => [...current, ...page.items.filter(item => !current.some(existing => existing.id === item.id))]);
            setAfter(page.next_after ?? null);
        }
        catch (cause) {
            if (!isStaleRequest(cause) && isApiGenerationCurrent(generation))
                setError(cause instanceof Error ? cause.message : "Could not load more resources");
        }
    }, [project, after]);
    const rememberOperation = useCallback((resourceId: string, operationId: string) => setOperationIds(current => ({ ...current, [resourceId]: operationId })), []);
    return { resources, options, operations, error, resourceError, catalogError, after, loading, refresh, loadMore, rememberOperation };
}
