"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, apiGeneration, isApiGenerationCurrent, isStaleRequest } from "@/lib/api/client";
import type { Activity } from "@/features/activity/types";
import { useWorkspace } from "@/features/workspace/session";
export function useActivity() {
    const { project } = useWorkspace();
    const [items, setItems] = useState<Activity[]>([]);
    const [error, setError] = useState("");
    const [loading, setLoading] = useState(true);
    const [visible, setVisible] = useState(10);
    const sequence = useRef(0);
    const requestController = useRef<AbortController | null>(null);
    const mounted = useRef(false);
    const refresh = useCallback(async () => {
        requestController.current?.abort();
        const controller = new AbortController();
        requestController.current = controller;
        const signal = controller.signal;
        const currentSequence = ++sequence.current;
        const generation = apiGeneration();
        const current = () => mounted.current && sequence.current === currentSequence && isApiGenerationCurrent(generation);
        if (!project) {
            setItems([]);
            setError("");
            setLoading(false);
            setVisible(10);
            return;
        }
        setLoading(true);
        try {
            const result = await api<{
                items: Activity[];
            }>(`projects/${project.project_id}/activity`, { signal });
            if (current()) {
                setItems(result.items);
                setError("");
            }
        }
        catch (cause) {
            if (current() && !isStaleRequest(cause))
                setError(cause instanceof Error ? cause.message : "Activity unavailable");
        }
        finally {
            if (current())
                setLoading(false);
        }
    }, [project]);
    useEffect(() => {
        mounted.current = true;
        void refresh();
        if (!project)
            return () => { mounted.current = false; sequence.current += 1; requestController.current?.abort(); };
        const timer = window.setInterval(() => void refresh(), 5000);
        return () => { mounted.current = false; sequence.current += 1; requestController.current?.abort(); window.clearInterval(timer); };
    }, [refresh, project]);
    return { items, error, loading, visible, setVisible, refresh };
}
