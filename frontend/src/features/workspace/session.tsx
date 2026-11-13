"use client";
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { api, apiGeneration, ApiError, advanceApiGeneration, beginAuthenticatedMutation, beginSessionTransition, isApiGenerationCurrent, setActiveProject, setAuthenticationExpiryHandler, setSession } from "@/lib/api/client";
import type { BrowserEnvelope, BrowserPrincipal } from "@/features/identity/types";
import type { Project } from "@/features/workspace/types";
type Workspace = {
    principal: BrowserPrincipal | null;
    projects: Project[];
    project: Project | null;
    loading: boolean;
    transitioning: boolean;
    error: string;
    refresh: () => Promise<void>;
    selectProject: (id: string) => Promise<void>;
    signOut: () => Promise<void>;
};
const Context = createContext<Workspace | null>(null);
export function WorkspaceProvider({ children }: {
    children: React.ReactNode;
}) {
    const [principal, setPrincipal] = useState<BrowserPrincipal | null>(null);
    const [projects, setProjects] = useState<Project[]>([]);
    const [project, setProject] = useState<Project | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");
    const [transitioning, setTransitioning] = useState(false);
    const transitionLock = useRef(false);
    const mounted = useRef(false);
    const refreshSequence = useRef(0);
    const clear = useCallback((message?: string) => {
        beginSessionTransition();
        setPrincipal(null);
        setProjects([]);
        setProject(null);
        setLoading(false);
        if (message)
            setError(message);
    }, []);
    const refresh = useCallback(async () => {
        const sequence = ++refreshSequence.current;
        const gen = apiGeneration();
        const current = () => mounted.current && sequence === refreshSequence.current && isApiGenerationCurrent(gen);
        setLoading(true);
        setError("");
        try {
            const envelope = await api<BrowserEnvelope>("me/browser");
            if (!current())
                return;
            setSession(envelope);
            const who = envelope.principal;
            const list = await api<Project[]>("projects");
            if (!current())
                return;
            const selected = list.find(p => p.project_id === who.projectId) ?? list[0] ?? null;
            setActiveProject(selected?.project_id ?? null);
            let nextPrincipal = who;
            if (selected && who.projectId !== selected.project_id) {
                const updated = await api<BrowserEnvelope>("auth/project", { method: "POST", body: JSON.stringify({ projectId: selected.project_id }) });
                if (!current())
                    return;
                setSession(updated);
                nextPrincipal = updated.principal;
            }
            setPrincipal(nextPrincipal);
            setProjects(list);
            setProject(selected);
        }
        catch (cause) {
            if (current()) {
                beginSessionTransition();
                setPrincipal(null);
                setProjects([]);
                setProject(null);
                if (!(cause instanceof ApiError && cause.status === 401))
                    setError(cause instanceof Error ? cause.message : "Workspace unavailable");
            }
        }
        finally {
            if (mounted.current && sequence === refreshSequence.current)
                setLoading(false);
        }
    }, []);
    useEffect(() => { mounted.current = true; setAuthenticationExpiryHandler(() => { refreshSequence.current += 1; beginSessionTransition(); setPrincipal(null); setProjects([]); setProject(null); setLoading(false); setError("Your session ended. Sign in again to continue."); }); void refresh(); return () => { mounted.current = false; refreshSequence.current += 1; setAuthenticationExpiryHandler(null); }; }, [refresh]);
    const selectProject = useCallback(async (id: string) => {
        const next = projects.find(p => p.project_id === id);
        if (transitionLock.current || !next || id === project?.project_id)
            return;
        transitionLock.current = true;
        setTransitioning(true);
        const previous = project?.project_id ?? null;
        const gen = advanceApiGeneration();
        setActiveProject(id);
        setProject(null);
        try {
            const envelope = await api<BrowserEnvelope>("auth/project", { method: "POST", body: JSON.stringify({ projectId: id }) });
            if (!isApiGenerationCurrent(gen))
                return;
            setSession(envelope);
            setPrincipal(envelope.principal);
            setProject(next);
            setError("");
        }
        catch (cause) {
            if (isApiGenerationCurrent(gen)) {
                setActiveProject(previous);
                setProject(project);
                setError(cause instanceof Error ? cause.message : "Project switch failed");
            }
        }
        finally {
            transitionLock.current = false;
            if (mounted.current)
                setTransitioning(false);
        }
    }, [projects, project]);
    const signOut = useCallback(async () => {
        if (transitionLock.current)
            return;
        transitionLock.current = true;
        setTransitioning(true);
        const gen = beginAuthenticatedMutation();
        try {
            await api("auth/logout", { method: "POST", body: "{}" });
            if (isApiGenerationCurrent(gen))
                clear();
        }
        catch (cause) {
            if (isApiGenerationCurrent(gen))
                setError(cause instanceof Error ? cause.message : "Sign out failed");
        }
        finally {
            transitionLock.current = false;
            if (mounted.current)
                setTransitioning(false);
        }
    }, [clear]);
    const value = useMemo(() => ({ principal, projects, project, loading, transitioning, error, refresh, selectProject, signOut }), [principal, projects, project, loading, transitioning, error, refresh, selectProject, signOut]);
    return <Context.Provider value={value}>{children}</Context.Provider>;
}
export function useWorkspace() {
    const value = useContext(Context);
    if (!value)
        throw new Error("WorkspaceProvider is missing");
    return value;
}
