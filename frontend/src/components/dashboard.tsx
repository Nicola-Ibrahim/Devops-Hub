"use client";

import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import IdentityAdministration from "./identity-administration";
import GuestDashboard from "./guest-dashboard";
import Link from "next/link";

export type DashboardSection = "overview" | "resources" | "applications" | "account" | "settings" | "activity";
const dashboardSections: DashboardSection[] = ["overview", "resources", "applications", "account", "settings", "activity"];
function safeDashboardNext() {
  const queryNext = new URLSearchParams(window.location.search).get("next");
  const candidate = window.location.pathname === "/login" ? queryNext ?? "/dashboard" : `${window.location.pathname}${window.location.search}`;
  return /^\/dashboard(?:\/(?:overview|resources|applications|account|settings|activity)|\/(?:resources|applications)\/[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})?(?:\?.*)?$/i.test(candidate) ? candidate : "/dashboard";
}

type Environment = { id: string; name: string };
type Project = { project_id: string; name: string; owning_team_name?: string | null; repository?: string | null; configured: boolean; environments: Environment[] };
type Option = { template_id: string; version: string; target_id: string; size: { id: string; cpu_millis: number; memory_bytes: number; storage_bytes: number; storage_enforcement: string }; max_lifetime_seconds: number; requestable: boolean; unavailable_reason?: string | null };
type Resource = { id: string; project_id: string; owner_id: string; environment_id?: string | null; display_name: string; template_id: string; target_id: string; size_id: string; desired_state: string; status: string; revision: number; created_at: string; expires_at: string; failure_code?: string | null };
type Operation = { id: string; resource_id: string; action: string; status: string; attempts: number; error_code?: string | null };
type Page<T> = { items: T[]; next_after?: string | null };
type Activity = { id: string; actor_id: string | null; resource_id: string; operation_id: string; action: string; created_at: string };
type ConnectionDetails = { connection_string: string; host: string; port: number; database: string; user: string; instructions: string };
type BrowserPrincipal = { userId: string; userName: string; sessionId: string; projectId?: string | null; projectName?: string | null; role?: string | null; scopes: string[]; csrfToken: string; memberships: { projectId: string; projectName: string; role: string }[] };
type BrowserEnvelope = { csrfToken?: string; principal: BrowserPrincipal; absoluteExpiresAt?: string };
type AppTemplate = { id: string; version: string; language: string; name: string; description: string };
type App = { id: string; project_id: string; environment_id: string; name: string; template_id: string; template_version: string; repository_url: string | null; status: string; created_at: string; expires_at?: string | null; resource_id?: string | null };
type DeliveryStep = { id: string; application_id: string; kind: string; status: string; attempts: number; error_code: string | null; created_at: string; updated_at: string };
type AppDetails = { application: App; steps: DeliveryStep[] };
type PreviewDeployment = { id: string; status: string; url?: string | null; created_at?: string; image_digest?: string | null; target_id?: string };
type LocalPreview = { application: App; deployments: PreviewDeployment[]; steps?: DeliveryStep[] };
let csrfToken = "";
let onAuthenticationExpired: (() => void) | null = null;
let apiGeneration = 0;
let activeProjectId: string | null = null;

export class StaleApiRequest extends Error {}

function isStaleApiRequest(cause: unknown) { return cause instanceof StaleApiRequest; }
function isCurrentGeneration(generation: number) { return generation === apiGeneration; }
function currentApiGeneration() { return apiGeneration; }
function rejectIfStale(generation: number) {
  if (!isCurrentGeneration(generation)) throw new StaleApiRequest();
}
function rejectIfProjectStale(generation: number, projectId: string | undefined) {
  rejectIfStale(generation);
  if (projectId && projectId !== activeProjectId) throw new StaleApiRequest();
}

class ApiError extends Error {
  constructor(message: string, readonly status: number) { super(message); }
}

async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const generation = apiGeneration;
  const pathProject = /^projects\/([^/]+)/.exec(path)?.[1];
  if (pathProject && pathProject !== activeProjectId) throw new StaleApiRequest();
  const headers = new Headers(init.headers);
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  if (init.method && init.method !== "GET" && csrfToken && !headers.has("X-CSRF-Token")) headers.set("X-CSRF-Token", csrfToken);
  let response: Response;
  try {
    response = await fetch(`/api/v1/${path}`, { ...init, headers, cache: "no-store", credentials: "same-origin" });
  } catch (cause) {
    rejectIfProjectStale(generation, pathProject);
    throw cause;
  }
  rejectIfProjectStale(generation, pathProject);
  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      rejectIfProjectStale(generation, pathProject);
      const nestedError = body.error && typeof body.error === "object" ? body.error.message : undefined;
      if (typeof body.detail === "string") detail = body.detail;
      else if (typeof body.message === "string") detail = body.message;
      else if (typeof nestedError === "string") detail = nestedError;
      else if (typeof body.code === "string") detail = body.code.replaceAll("_", " ");
    } catch { /* response has no JSON detail */ }
    rejectIfProjectStale(generation, pathProject);
    if (response.status === 401 && path !== "auth/login") {
      onAuthenticationExpired?.();
      throw new StaleApiRequest();
    }
    throw new ApiError(detail, response.status);
  }
  if (response.status === 204) return undefined as T;
  let body: T;
  try { body = await response.json() as T; }
  catch (cause) { rejectIfProjectStale(generation, pathProject); throw cause; }
  rejectIfProjectStale(generation, pathProject);
  return body;
}

function formatBytes(bytes: number) {
  if (bytes >= 1024 ** 3) return `${(bytes / 1024 ** 3).toFixed(1)} GB`;
  return `${Math.round(bytes / 1024 ** 2)} MB`;
}
function formatDate(value: string) { return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value)); }
function formatDuration(seconds: number) { return seconds < 3600 ? `${Math.floor(seconds / 60)} minutes` : seconds % 3600 === 0 ? `${seconds / 3600} hour${seconds === 3600 ? "" : "s"}` : `${Math.floor(seconds / 3600)}h ${Math.floor(seconds % 3600 / 60)}m`; }
function makeIdempotencyKey() { return crypto.randomUUID(); }

export default function Dashboard({ section = "overview" }: { section?: DashboardSection }) {
  const [guest, setGuest] = useState(false);
  const [principal, setPrincipal] = useState<BrowserPrincipal | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [project, setProject] = useState<Project | null>(null);
  const [resources, setResources] = useState<Resource[]>([]);
  const [options, setOptions] = useState<Option[]>([]);
  const [operations, setOperations] = useState<Record<string, Operation>>({});
  const [activity, setActivity] = useState<Activity[]>([]);
  const [resourceAfter, setResourceAfter] = useState<string | null>(null);
  const [activityVisible, setActivityVisible] = useState(10);
  const [activityError, setActivityError] = useState("");
  const [catalogError, setCatalogError] = useState("");
  const [historyErrors, setHistoryErrors] = useState<Record<string, string>>({});
  const resourcePagesRef = useRef<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [bootstrapError, setBootstrapError] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [form, setForm] = useState({ environment_id: "", display_name: "", option: "", ttl_seconds: 3600 });
  const [connection, setConnection] = useState<{ resourceId: string; value: string; details: ConnectionDetails } | null>(null);
  const [renewing, setRenewing] = useState<Resource | null>(null);
  const [renewSeconds, setRenewSeconds] = useState(7200);
  const [pendingRequest, setPendingRequest] = useState<{ key: string; body: string } | null>(null);
  const [operationIds, setOperationIds] = useState<Record<string, string>>({});
  const [appTemplates, setAppTemplates] = useState<AppTemplate[]>([]);
  const [applications, setApplications] = useState<AppDetails[]>([]);
  const [appName, setAppName] = useState("");
  const [appTemplate, setAppTemplate] = useState("");
  const [appEnvironment, setAppEnvironment] = useState("");
  const [pendingApplication, setPendingApplication] = useState<{ key: string; body: string } | null>(null);
  const [localPreviews, setLocalPreviews] = useState<LocalPreview[]>([]);
  const [previewName, setPreviewName] = useState("");
  const [previewDigests, setPreviewDigests] = useState<Record<string, string>>({});
  const [previewEnvironment, setPreviewEnvironment] = useState("");
  const [previewTtl, setPreviewTtl] = useState(3600);
  const [previewBusyId, setPreviewBusyId] = useState("");
  const [pendingPreview, setPendingPreview] = useState<{ key: string; body: string } | null>(null);
  const [identityBusy, setIdentityBusy] = useState(false);
  const identityMutationLock = useRef<symbol | null>(null);
  const previewIdempotencyKeys = useRef<Record<string, string>>({});
  const pendingAttachmentRequests = useRef<Record<string, { key: string; body: string }>>({});
  const dialogRef = useRef<HTMLElement | null>(null);
  const modalReturnFocus = useRef<HTMLElement | null>(null);

  function previewMutationKey(operation: string, applicationId: string, body: string) {
    const identity = `${operation}:${applicationId}:${body}`;
    return previewIdempotencyKeys.current[identity] ?? (previewIdempotencyKeys.current[identity] = makeIdempotencyKey());
  }

  const clearAuthentication = useCallback((message = "Your session ended. Sign in again to continue.") => {
    apiGeneration += 1;
    activeProjectId = null;
    csrfToken = "";
    identityMutationLock.current = null;
    setIdentityBusy(false);
    setBusy(false);
    setLoading(false);
    setPrincipal(null); setProjects([]); setProject(null); setResources([]); setOptions([]);
    setOperations({}); setOperationIds({}); setActivity([]); setConnection(null); setRenewing(null);
    resourcePagesRef.current = []; setResourceAfter(null); setActivityVisible(10); setActivityError(""); setCatalogError(""); setHistoryErrors({});
    setApplications([]); setAppTemplates([]); setPendingRequest(null); setPendingApplication(null);
    setLocalPreviews([]); setPendingPreview(null);
    setPreviewDigests({}); setPreviewBusyId(""); pendingAttachmentRequests.current = {}; previewIdempotencyKeys.current = {};
    setPassword(""); setError(message); setNotice("");
  }, []);

  useEffect(() => {
    onAuthenticationExpired = () => clearAuthentication();
    return () => { onAuthenticationExpired = null; };
  }, [clearAuthentication]);

  const loadSession = useCallback(async () => {
    const generation = apiGeneration;
    try {
      const envelope = await api<BrowserEnvelope>("me/browser");
      rejectIfStale(generation);
      csrfToken = envelope.csrfToken ?? envelope.principal.csrfToken;
      const who = envelope.principal;
      setPrincipal(who);
      const projectList = await api<Project[]>("projects");
      rejectIfStale(generation);
      setProjects(projectList);
      const selected = projectList.find((item) => item.project_id === who.projectId) ?? projectList[0] ?? null;
      activeProjectId = selected?.project_id ?? null;
      if (selected && who.projectId !== selected.project_id) {
        const updated = await api<BrowserEnvelope>("auth/project", { method: "POST", body: JSON.stringify({ projectId: selected.project_id }) });
        rejectIfStale(generation);
        csrfToken = updated.csrfToken ?? updated.principal.csrfToken;
        setPrincipal(updated.principal);
      }
      rejectIfStale(generation);
      setProject(selected);
    } catch (cause) {
      if (cause instanceof StaleApiRequest || !isCurrentGeneration(generation)) return;
      csrfToken = ""; activeProjectId = null;
      setPrincipal(null); setProjects([]); setProject(null); setResources([]); setOptions([]); setOperations({}); setOperationIds({}); setActivity([]); setConnection(null); setApplications([]); setAppTemplates([]);
      if (!(cause instanceof ApiError && cause.status === 401)) { setBootstrapError(cause instanceof Error ? cause.message : "Could not connect to the workspace API"); setError(""); }
    } finally { if (isCurrentGeneration(generation)) setLoading(false); }
  }, []);

  useEffect(() => { void loadSession(); }, [loadSession]);

  useEffect(() => {
    if (loading || principal || guest || bootstrapError || typeof window === "undefined") return;
    const next = safeDashboardNext();
    if (window.location.pathname !== "/login") window.location.replace(`/login?next=${encodeURIComponent(next)}`);
  }, [loading, principal, guest, bootstrapError]);

  useEffect(() => {
    if (principal && !loading && typeof window !== "undefined" && window.location.pathname === "/login") window.location.replace(safeDashboardNext());
  }, [principal, loading]);

  useEffect(() => {
    if (!connection && !renewing) return;
    modalReturnFocus.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const dialog = dialogRef.current;
    const focusable = () => dialog?.querySelectorAll<HTMLElement>('a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])') ?? [];
    focusable()[0]?.focus();
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") { event.preventDefault(); setConnection(null); setRenewing(null); return; }
      if (event.key !== "Tab") return;
      const items = focusable();
      if (!items.length) { event.preventDefault(); return; }
      if (event.shiftKey && document.activeElement === items[0]) { event.preventDefault(); items[items.length - 1].focus(); }
      else if (!event.shiftKey && document.activeElement === items[items.length - 1]) { event.preventDefault(); items[0].focus(); }
    }
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      modalReturnFocus.current?.focus();
      modalReturnFocus.current = null;
    };
  }, [connection, renewing]);

  const refreshApplications = useCallback(async () => {
    if (!project) { if (activeProjectId === null) { setApplications([]); setAppTemplates([]); } return; }
    const generation = apiGeneration;
    const projectId = project.project_id;
    if (activeProjectId !== projectId) return;
    try {
      const [catalog, rows] = await Promise.all([
        api<AppTemplate[]>("templates"),
        api<App[]>("applications"),
      ]);
      rejectIfStale(generation);
      if (activeProjectId !== projectId) throw new StaleApiRequest();
      setAppTemplates(catalog);
      const details = await Promise.all(rows.map((app) => api<AppDetails>(`applications/${app.id}`)));
      rejectIfStale(generation);
      if (activeProjectId !== projectId) throw new StaleApiRequest();
      setApplications(details.filter((item) => item.application.template_id !== "local-image"));
      const detailsById = new Map(details.map((item) => [item.application.id, item]));
      const previewResults = await Promise.all(rows.map(async (app) => {
        try { return { id: app.id, history: await api<PreviewDeployment[]>(`applications/${app.id}/deployments`), error: "" }; }
        catch (cause) {
          if (cause instanceof StaleApiRequest) throw cause;
          return { id: app.id, history: [] as PreviewDeployment[], error: cause instanceof Error ? cause.message : "Could not load deployment history" };
        }
      }));
      rejectIfStale(generation);
      const previewErrors = Object.fromEntries(previewResults.filter((result) => result.error).map((result) => [result.id, result.error]));
      setHistoryErrors(previewErrors);
      const histories = new Map(previewResults.map((result) => [result.id, result.history.filter((deployment) => deployment.target_id === "local")]));
      setLocalPreviews((current) => {
        return details.map((detail) => ({ application: detail.application, steps: detail.steps, deployments: histories.get(detail.application.id) ?? current.find((item) => item.application.id === detail.application.id)?.deployments ?? [] }));
      });
      if (!appTemplate && catalog.length) setAppTemplate(`${catalog[0].id}@${catalog[0].version}`);
    } catch (cause) {
      if (cause instanceof StaleApiRequest || !isCurrentGeneration(generation) || activeProjectId !== projectId) return;
      setError(cause instanceof Error ? cause.message : "Could not load applications");
    }
  }, [project, appTemplate]);

  async function refreshPreview(preview: LocalPreview) {
    const generation = apiGeneration;
    const projectId = project?.project_id;
    if (!projectId || activeProjectId !== projectId) return;
    const [details, history] = await Promise.all([
      api<AppDetails>(`applications/${preview.application.id}`),
      api<LocalPreview["deployments"]>(`applications/${preview.application.id}/deployments`),
    ]);
    rejectIfStale(generation);
    if (activeProjectId !== projectId) throw new StaleApiRequest();
    const deployments = history.filter((item) => item.target_id === "local");
    setHistoryErrors((current) => { const updated = { ...current }; delete updated[preview.application.id]; return updated; });
    setLocalPreviews((current) => current.map((item) => item.application.id === preview.application.id ? { ...item, application: details.application, steps: details.steps, deployments } : item));
  }

  async function registerLocalPreview(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!project || !previewName.trim() || !previewEnvironment) return;
    const lock = acquireFlowLock(); if (!lock) return;
    const generation = apiGeneration;
    const body = JSON.stringify({ name: previewName.trim(), environment_id: previewEnvironment, ttl_seconds: previewTtl });
    const key = pendingPreview?.body === body ? pendingPreview.key : makeIdempotencyKey();
    setPendingPreview({ key, body }); setBusy(true); setError(""); setNotice("");
    try {
      const accepted = await api<{ application: App }>("applications/local-preview", { method: "POST", headers: { "Idempotency-Key": key }, body });
      rejectIfStale(generation);
      const preview: LocalPreview = { application: accepted.application, deployments: [] };
      setLocalPreviews((current) => [preview, ...current.filter((item) => item.application.id !== preview.application.id)]);
      setPendingPreview(null); setPreviewName("");
      setNotice("Local preview registered. Choose whether to attach a database, then deploy when ready.");
    } catch (cause) {
      if (cause instanceof StaleApiRequest || !isCurrentGeneration(generation)) return;
      setError(`${cause instanceof Error ? cause.message : "Registration failed"}. Retry to reuse the request key.`);
    } finally { releaseFlowLock(lock); if (isCurrentGeneration(generation)) setBusy(false); }
  }

  async function attachPreviewDatabase(preview: LocalPreview) {
    const localOption = options.find((option) => option.target_id === "local" && option.requestable);
    if (!project || !localOption) { setError("No approved local PostgreSQL option is available. You can deploy without a database."); return; }
    const remainingLease = preview.application.expires_at ? Math.floor((Date.parse(preview.application.expires_at) - Date.now()) / 1000) - 10 : Math.min(3600, localOption.max_lifetime_seconds);
    if (remainingLease < 60) { setError("This preview has less than 70 seconds remaining. Register a new preview or deploy without a database."); return; }
    const generation = apiGeneration;
    setPreviewBusyId(preview.application.id); setError("");
    try {
      const candidateBody = JSON.stringify({ template_id: localOption.template_id, version: localOption.version, target_id: "local", size_id: localOption.size.id, ttl_seconds: Math.min(remainingLease, localOption.max_lifetime_seconds) });
      const pending = pendingAttachmentRequests.current[preview.application.id];
      const body = pending?.body ?? candidateBody;
      const key = pending?.key ?? previewMutationKey("attach", preview.application.id, body);
      pendingAttachmentRequests.current[preview.application.id] = { body, key };
      const step = await api<DeliveryStep>(`applications/${preview.application.id}/resources`, { method: "POST", headers: { "Idempotency-Key": key }, body });
      rejectIfStale(generation);
      setLocalPreviews((current) => current.map((item) => item.application.id === preview.application.id ? { ...item, steps: [...(item.steps ?? []).filter((existing) => existing.id !== step.id), step] } : item));
      delete pendingAttachmentRequests.current[preview.application.id];
      delete previewIdempotencyKeys.current[`attach:${preview.application.id}:${body}`];
      await Promise.all([refreshPreview(preview), refreshProject()]);
      setNotice("Database attachment requested. Deployment will unlock when its resource is ready.");
    } catch (cause) {
      if (cause instanceof StaleApiRequest || !isCurrentGeneration(generation)) return;
      setError(cause instanceof Error ? cause.message : "Database attachment failed");
    } finally { if (isCurrentGeneration(generation)) setPreviewBusyId(""); }
  }

  async function deployLocalPreview(preview: LocalPreview) {
    const digest = previewDigests[preview.application.id]?.trim();
    if (!digest) { setError("Enter an immutable image digest before deploying."); return; }
    const attachedResource = resources.find((item) => item.id === preview.application.resource_id);
    const attachmentStep = [...(preview.steps ?? [])].reverse().find((step) => step.kind === "resource");
    if (attachmentStep && ["pending", "running"].includes(attachmentStep.status)) return;
    if (preview.application.resource_id && attachedResource?.status !== "ready") return;
    const generation = apiGeneration;
    setPreviewBusyId(preview.application.id); setError("");
    try {
      const body = JSON.stringify({ image_digest: digest, target_id: "local" });
      await api<PreviewDeployment>(`applications/${preview.application.id}/deployments`, { method: "POST", headers: { "Idempotency-Key": previewMutationKey("deploy", preview.application.id, body) }, body });
      rejectIfStale(generation);
      delete previewIdempotencyKeys.current[`deploy:${preview.application.id}:${body}`];
      await refreshPreview(preview);
      setNotice("Local deployment queued. Status will update automatically.");
    } catch (cause) {
      if (cause instanceof StaleApiRequest || !isCurrentGeneration(generation)) return;
      setError(cause instanceof Error ? cause.message : "Deployment failed. Retry is available.");
    } finally { if (isCurrentGeneration(generation)) setPreviewBusyId(""); }
  }

  useEffect(() => {
    if (!localPreviews.length || !project) return;
    const timer = window.setInterval(() => {
      for (const preview of localPreviews) void refreshPreview(preview).catch((cause) => { if (!(cause instanceof StaleApiRequest)) setHistoryErrors((current) => ({ ...current, [preview.application.id]: cause instanceof Error ? cause.message : "Could not load deployment history" })); });
    }, 5000);
    return () => window.clearInterval(timer);
  }, [localPreviews, project]);

  useEffect(() => {
    void refreshApplications();
    const timer = window.setInterval(() => { void refreshApplications(); }, 5000);
    return () => window.clearInterval(timer);
  }, [refreshApplications]);

  async function createApplication(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!project || !appName.trim() || !appTemplate || !appEnvironment) return;
    const lock = acquireFlowLock(); if (!lock) return;
    const generation = apiGeneration;
    const projectId = project.project_id;
    const [template_id, template_version] = appTemplate.split("@");
    setBusy(true); setError(""); setNotice("");
    const body = JSON.stringify({ name: appName.trim(), environment_id: appEnvironment, template_id, template_version });
    const key = pendingApplication?.body === body ? pendingApplication.key : makeIdempotencyKey();
    setPendingApplication({ key, body });
    try {
      const accepted = await api<{ application: App; replayed: boolean }>("applications", {
        method: "POST",
        headers: { "Idempotency-Key": key },
        body,
      });
      rejectIfStale(generation);
      if (activeProjectId !== projectId) throw new StaleApiRequest();
      setPendingApplication(null);
      setAppName("");
      setNotice(`Application ${accepted.application.name} is queued. Repository creation progress will appear here.`);
      await refreshApplications();
    } catch (cause) {
      if (cause instanceof StaleApiRequest || !isCurrentGeneration(generation) || activeProjectId !== projectId) return;
      setError(cause instanceof Error ? cause.message : "Application request failed");
    } finally { releaseFlowLock(lock); if (isCurrentGeneration(generation)) setBusy(false); }
  }

  async function retryDeliveryStep(application: App, step: DeliveryStep) {
    if (step.status !== "failed" || busy || identityBusy) return;
    const lock = acquireFlowLock(); if (!lock) return;
    const generation = apiGeneration;
    setError(""); setNotice("");
    try {
      await api<DeliveryStep>(`applications/${application.id}/steps/${step.id}/retry`, { method: "POST" });
      rejectIfStale(generation);
      setNotice(`Retry requested for ${step.kind.replaceAll("_", " ")}.`);
      await refreshApplications();
    } catch (cause) {
      if (cause instanceof StaleApiRequest || !isCurrentGeneration(generation)) return;
      setError(cause instanceof Error ? cause.message : "Could not retry delivery step");
    } finally { releaseFlowLock(lock); if (isCurrentGeneration(generation)) setBusy(false); }
  }


  const refreshProject = useCallback(async () => {
    if (!project) { if (activeProjectId === null) { setResources([]); setOptions([]); } return; }
    const generation = apiGeneration;
    const projectId = project.project_id;
    if (activeProjectId !== projectId) return;
    try {
      const requestedCursors: (string | null)[] = [null, ...resourcePagesRef.current];
      const catalogResult = await Promise.allSettled([
        api<{ templates: Option[] }>("catalog"),
        api<{ items: Activity[] }>(`projects/${project.project_id}/activity`),
      ]);
      const pages: Page<Resource>[] = [];
      for (let pageIndex = 0; pageIndex < requestedCursors.length; pageIndex += 1) {
        const cursor = pages.at(-1)?.next_after ?? null;
        const query = new URLSearchParams({ limit: "25" });
        if (cursor) query.set("after", cursor);
        const page = await api<Page<Resource>>(`projects/${project.project_id}/resources?${query}`);
        pages.push(page);
        if (!page.next_after) break;
      }
      rejectIfStale(generation);
      if (activeProjectId !== projectId) throw new StaleApiRequest();
      const resourceRows = pages.flatMap((page) => page.items);
      const cursorsUsed = pages.slice(0, Math.max(0, pages.length - 1)).map((page) => page.next_after).filter((cursor): cursor is string => !!cursor);
      resourcePagesRef.current = cursorsUsed;
      setResourceAfter(pages.at(-1)?.next_after ?? null);
      setResources(resourceRows);
      if (catalogResult[0].status === "fulfilled") { setOptions(catalogResult[0].value.templates ?? []); setCatalogError(""); }
      else if (!(catalogResult[0].reason instanceof StaleApiRequest)) setCatalogError(catalogResult[0].reason instanceof Error ? catalogResult[0].reason.message : "Could not load resource catalog");
      if (catalogResult[1].status === "fulfilled") { setActivity(catalogResult[1].value.items); setActivityError(""); }
      else if (!(catalogResult[1].reason instanceof StaleApiRequest)) setActivityError(catalogResult[1].reason instanceof Error ? catalogResult[1].reason.message : "Could not load project activity");
      const operationsToLoad = new Map<string, string>();
      for (const resource of resourceRows) {
        const id = operationIds[resource.id];
        if (id) operationsToLoad.set(resource.id, id);
      }
      for (const event of (catalogResult[1].status === "fulfilled" ? catalogResult[1].value.items : []).slice(0, activityVisible)) {
        if (event.resource_id && event.operation_id && !operationsToLoad.has(event.resource_id)) operationsToLoad.set(event.resource_id, event.operation_id);
      }
      const ops = await Promise.all([...operationsToLoad].map(async ([resourceId, operationId]) => {
        const op = await api<Operation>(`operations/${operationId}`);
        return [resourceId, op] as const;
      }));
      rejectIfStale(generation);
      if (activeProjectId !== projectId) throw new StaleApiRequest();
      setOperations(Object.fromEntries(ops));
    } catch (cause) {
      if (cause instanceof StaleApiRequest || !isCurrentGeneration(generation) || activeProjectId !== projectId) return;
      setError(cause instanceof Error ? cause.message : "Could not load project resources");
    }
  }, [project, operationIds, activityVisible]);

  async function loadMoreResources() {
    if (!project || !resourceAfter) return;
    const cursor = resourceAfter;
    const generation = apiGeneration;
    const query = new URLSearchParams({ limit: "25", after: cursor });
    try {
      const page = await api<Page<Resource>>(`projects/${project.project_id}/resources?${query}`);
      rejectIfStale(generation);
      resourcePagesRef.current = [...resourcePagesRef.current, cursor];
      setResources((current) => [...current, ...page.items.filter((item) => !current.some((existing) => existing.id === item.id))]);
      setResourceAfter(page.next_after ?? null);
    } catch (cause) { if (!(cause instanceof StaleApiRequest) && isCurrentGeneration(generation)) setError(cause instanceof Error ? cause.message : "Could not load more resources"); }
  }

  function extensionChoices(resource: Resource) { return leaseExtensionChoices(resource, options); }

  useEffect(() => { void refreshProject(); const timer = window.setInterval(() => { void refreshProject(); }, 5000); return () => window.clearInterval(timer); }, [refreshProject]);

  useEffect(() => {
    if (!project) return;
    setForm((current) => {
      const selected = options.find((option) => optionKey(option) === current.option && option.requestable) ?? options.find((option) => option.requestable);
      return { ...current, environment_id: project.environments.some((env) => env.id === current.environment_id) ? current.environment_id : project.environments[0]?.id ?? "", option: selected ? optionKey(selected) : "", ttl_seconds: selected ? Math.min(current.ttl_seconds, selected.max_lifetime_seconds) : current.ttl_seconds };
    });
    setAppEnvironment((current) => project.environments.some((env) => env.id === current) ? current : project.environments[0]?.id ?? "");
  }, [project, options]);

  const selectedOption = useMemo(() => options.find((item) => optionKey(item) === form.option), [options, form.option]);
  const canRequest = !!project?.configured && !!form.environment_id && !!form.display_name.trim() && !!selectedOption?.requestable && !busy && !identityBusy;

  function acquireFlowLock() {
    if (identityMutationLock.current) return null;
    const lock = Symbol("dashboard-mutation");
    identityMutationLock.current = lock;
    setIdentityBusy(true);
    return lock;
  }

  function releaseFlowLock(lock: symbol) {
    if (identityMutationLock.current !== lock) return;
    identityMutationLock.current = null;
    setIdentityBusy(false);
  }

  async function login(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(""); setBusy(true);
    const generation = ++apiGeneration;
    activeProjectId = null;
    csrfToken = "";
    identityMutationLock.current = null; setIdentityBusy(false);
    setProject(null); setProjects([]); setResources([]); setOptions([]); setApplications([]); setAppTemplates([]);
    setOperations({}); setOperationIds({}); setActivity([]); setConnection(null);
    try {
      const result = await api<BrowserEnvelope>("auth/login", { method: "POST", body: JSON.stringify({ userName: username, password }) });
      rejectIfStale(generation);
      csrfToken = result.csrfToken ?? result.principal.csrfToken;
      setPassword(""); setPrincipal(result.principal); await loadSession();
      const next = safeDashboardNext();
      window.location.replace(next);
    } catch (cause) {
      if (cause instanceof StaleApiRequest || !isCurrentGeneration(generation)) return;
      setError(cause instanceof Error ? cause.message : "Sign in failed");
    } finally { if (isCurrentGeneration(generation)) setBusy(false); }
  }

  async function signOut() {
    if (identityMutationLock.current) return;
    const generation = ++apiGeneration;
    activeProjectId = null;
    setConnection(null); setError(""); setNotice(""); setBusy(true);
    try {
      await api("auth/logout", { method: "POST", body: "{}" });
      rejectIfStale(generation);
      clearAuthentication("You have signed out.");
    } catch (cause) {
      if (cause instanceof StaleApiRequest || !isCurrentGeneration(generation)) return;
      activeProjectId = project?.project_id ?? null;
      setError(cause instanceof Error ? cause.message : "Sign out failed");
    } finally { if (isCurrentGeneration(generation)) setBusy(false); }
  }

  async function submitRequest(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!project || !selectedOption || !canRequest) return;
    const lock = acquireFlowLock(); if (!lock) return;
    const generation = apiGeneration;
    const projectId = project.project_id;
    setError(""); setNotice(""); setBusy(true);
    const body = JSON.stringify({ project_id: project.project_id, environment_id: form.environment_id, display_name: form.display_name.trim(), template_id: selectedOption.template_id, version: selectedOption.version, target_id: selectedOption.target_id, size_id: selectedOption.size.id, ttl_seconds: Math.min(form.ttl_seconds, selectedOption.max_lifetime_seconds) });
    const key = pendingRequest?.body === body ? pendingRequest.key : makeIdempotencyKey();
    setPendingRequest({ key, body });
    try {
      const accepted = await api<{ resource_id: string; operation_id: string }>("resources", {
        method: "POST", headers: { "Idempotency-Key": key },
        body,
      });
      rejectIfStale(generation);
      if (activeProjectId !== projectId) throw new StaleApiRequest();
      setOperationIds((current) => ({ ...current, [accepted.resource_id]: accepted.operation_id }));
      setPendingRequest(null); setForm((current) => ({ ...current, display_name: "" })); setNotice(`Request accepted. Operation ${accepted.operation_id} is being processed.`); await refreshProject();
    } catch (cause) {
      if (cause instanceof StaleApiRequest || !isCurrentGeneration(generation) || activeProjectId !== projectId) return;
      setError(`${cause instanceof Error ? cause.message : "Request failed"}. Retry this submission to safely reuse its request key.`);
    } finally { releaseFlowLock(lock); if (isCurrentGeneration(generation)) setBusy(false); }
  }

  async function revealConnection(resource: Resource) {
    const generation = apiGeneration;
    const projectId = project?.project_id;
    if (!projectId || activeProjectId !== projectId) return;
    setError(""); setConnection(null); setBusy(true);
    try {
      const value = await api<ConnectionDetails>(`resources/${resource.id}/connection`, { method: "POST", body: "{}" });
      rejectIfStale(generation);
      if (activeProjectId !== projectId) throw new StaleApiRequest();
      setConnection({ resourceId: resource.id, value: value.connection_string, details: value });
    } catch (cause) {
      if (cause instanceof StaleApiRequest || !isCurrentGeneration(generation) || activeProjectId !== projectId) return;
      setError(cause instanceof Error ? cause.message : "Connection details could not be retrieved");
    } finally { if (isCurrentGeneration(generation)) setBusy(false); }
  }

  async function copyConnection() {
    if (!connection) return;
    const generation = apiGeneration;
    try {
      await navigator.clipboard.writeText(connection.value);
      if (!isCurrentGeneration(generation)) return;
      setNotice("Connection string copied. Handle it like a password.");
    } catch {
      if (isCurrentGeneration(generation)) setError("Clipboard access was blocked. Select the connection string and copy it manually.");
    }
  }

  async function renewResource(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!renewing) return;
    const lock = acquireFlowLock(); if (!lock) return;
    const generation = apiGeneration;
    const projectId = project?.project_id;
    const expiresAt = new Date(Date.parse(renewing.created_at) + renewSeconds * 1000).toISOString();
    setBusy(true); setError("");
    try {
      await api(`resources/${renewing.id}/renew`, { method: "POST", body: JSON.stringify({ expected_revision: renewing.revision, expires_at: expiresAt }) });
      rejectIfStale(generation);
      if (activeProjectId !== projectId) throw new StaleApiRequest();
      setRenewing(null); setNotice("Resource lease updated."); await refreshProject();
    } catch (cause) {
      if (cause instanceof StaleApiRequest || !isCurrentGeneration(generation) || activeProjectId !== projectId) return;
      setError(cause instanceof Error ? cause.message : "Lease update failed");
    } finally { releaseFlowLock(lock); if (isCurrentGeneration(generation)) setBusy(false); }
  }

  async function deleteResource(resource: Resource) {
    const accepted = window.confirm(`Delete ${resource.display_name}? This permanently removes its database container, dedicated volume and stored data. This cannot be undone.`);
    if (!accepted) return;
    const lock = acquireFlowLock(); if (!lock) return;
    const generation = apiGeneration;
    const projectId = project?.project_id;
    setBusy(true); setError("");
    try {
      await api(`resources/${resource.id}`, { method: "DELETE" });
      rejectIfStale(generation);
      if (activeProjectId !== projectId) throw new StaleApiRequest();
      setNotice(`Deletion requested for ${resource.display_name}. Cleanup status will remain visible here.`); await refreshProject();
    } catch (cause) {
      if (cause instanceof StaleApiRequest || !isCurrentGeneration(generation) || activeProjectId !== projectId) return;
      setError(`${cause instanceof Error ? cause.message : "Deletion request failed"}. The resource remains listed so cleanup can be retried.`);
    } finally { releaseFlowLock(lock); if (isCurrentGeneration(generation)) setBusy(false); }
  }

  async function switchProject(projectId: string) {
    const next = projects.find((item) => item.project_id === projectId); if (!next) return;
    if (identityMutationLock.current) return;
    const lock = Symbol("project-switch");
    identityMutationLock.current = lock;
    setIdentityBusy(true);
    const generation = ++apiGeneration;
    const previousProjectId = activeProjectId;
    activeProjectId = projectId;
    setConnection(null); setResources([]); setOptions([]); setOperations({}); setActivity([]);
    resourcePagesRef.current = []; setResourceAfter(null); setActivityVisible(10); setActivityError(""); setCatalogError(""); setHistoryErrors({});
    setApplications([]); setAppTemplates([]); setRenewing(null); setLocalPreviews([]); setPreviewDigests({}); setPreviewBusyId("");
    pendingAttachmentRequests.current = {}; previewIdempotencyKeys.current = {};
    setBusy(true); setError("");
    try {
      const result = await api<BrowserEnvelope>("auth/project", { method: "POST", body: JSON.stringify({ projectId }) });
      rejectIfStale(generation);
      csrfToken = result.csrfToken ?? result.principal.csrfToken;
      setPrincipal(result.principal); setProject(next);
    } catch (cause) {
      if (cause instanceof StaleApiRequest || !isCurrentGeneration(generation)) return;
      activeProjectId = previousProjectId;
      setProject(project);
      setError(cause instanceof Error ? cause.message : "Project switch failed");
      void refreshProject(); void refreshApplications();
    } finally {
      if (identityMutationLock.current === lock) { identityMutationLock.current = null; setIdentityBusy(false); }
      if (isCurrentGeneration(generation)) setBusy(false);
    }
  }

  if (guest && !principal) return <GuestDashboard onSignIn={() => setGuest(false)} />;
  if (loading) return <main className="center-screen"><div className="loader" aria-label="Loading" /></main>;
  if (bootstrapError) return <main className="center-screen"><section className="panel"><h1>Workspace unavailable</h1><p role="alert">{bootstrapError}</p><button className="primary-button" onClick={() => { setBootstrapError(""); setLoading(true); void loadSession(); }}>Retry</button><Link href="/">Home</Link></section></main>;
  if (!principal) return <Login visitAsGuest={() => { setPassword(""); setError(""); setGuest(true); }} username={username} password={password} setUsername={setUsername} setPassword={setPassword} submit={login} error={error} busy={busy} />;

  return <main className="shell">
    <aside className="sidebar">
      <div className="brand"><span className="brand-mark">D</span><span>devops<span className="brand-light">hub</span></span></div>
      <div className="workspace-label">WORKSPACE</div>
      <label className="project-select-label" htmlFor="project-select">Project</label>
      <select id="project-select" className="project-select" value={project?.project_id ?? ""} onChange={(event) => void switchProject(event.target.value)} disabled={busy || identityBusy || projects.length === 0}>
        {projects.map((item) => <option key={item.project_id} value={item.project_id}>{item.name}</option>)}
      </select>
      <nav className="nav">{dashboardSections.map((item) => <Link key={item} className={`nav-item ${section === item ? "active" : ""}`} aria-current={section === item ? "page" : undefined} href={item === "overview" ? "/dashboard" : `/dashboard/${item}`}>{item === "overview" ? "Overview" : item[0].toUpperCase() + item.slice(1)}</Link>)}</nav>
      <div className="sidebar-bottom"><Link href="/" className="nav-item">Home</Link><Link href="/dashboard/account" className="avatar" aria-label="Account">{principal.userName.slice(0, 1).toUpperCase()}</Link><div className="user-copy"><strong>{principal.userName}</strong><span>{principal.role ?? "Developer"}</span></div><button className="icon-button" onClick={() => void signOut()} disabled={identityBusy} title="Sign out" aria-label="Sign out">↪</button></div>
    </aside>

    <section className="main-content">
      <header className="topbar"><div className="breadcrumb">Workspace <span>/</span> {section}</div><div className="topbar-right"><span className="secure-label">{project?.name ?? "No project selected"}</span><Link href="/dashboard/account" className="user-menu" aria-label="Account">{principal.userName.slice(0, 1).toUpperCase()}</Link></div></header>
      <div className="content-wrap">
        <div className="page-heading"><div><div className="eyebrow">DEVELOPER PLATFORM</div><h1>{{ overview: "Workspace overview", resources: "Your resources", applications: "Applications", account: "Account security", settings: "Project settings", activity: "Project activity" }[section]}</h1><p>{section === "resources" ? "Temporary development environments managed by your team." : section === "applications" ? "Approved templates, local previews and delivery progress." : section === "account" ? "Manage your identity security and active sessions." : section === "settings" ? "Manage membership for the selected project." : "Project resources, application delivery and recent activity."}</p></div><span className="environment-pill">{project?.configured ? "Project configured" : "Setup required"}</span></div>
        {error && <div role="alert" className="alert error"><span>!</span><p>{error}</p><button onClick={() => setError("")} aria-label="Dismiss">×</button></div>}
        {notice && <div role="status" className="alert success"><span>✓</span><p>{notice}</p><button onClick={() => setNotice("")} aria-label="Dismiss">×</button></div>}
        {project && <div className="project-context"><div className="project-symbol">{project.name.slice(0, 1).toUpperCase()}</div><div><strong>{project.name}</strong><span>{project.owning_team_name || "Team not specified"}{project.repository ? ` · ${project.repository}` : ""}</span></div><div className="project-envs">{project.environments.map((env) => <span key={env.id}>{env.name}</span>)}</div></div>}

        {section === "overview" && <section className="dashboard-stats" aria-label="Workspace summary"><article className="panel"><strong>{resources.length}</strong><span>Loaded resources</span></article><article className="panel"><strong>{localPreviews.length}</strong><span>Applications and previews</span></article><article className="panel"><strong>{activity.length}</strong><span>Recent activity</span></article></section>}
        {(section === "resources" || section === "overview") && <div className="dashboard-grid">
          <section className="panel request-panel">
            <div className="panel-heading"><div><div className="eyebrow">RESOURCE CATALOG</div><h2>Request a database</h2></div><span className="catalog-icon">＋</span></div>
            {!project?.configured && <div className="notice-box"><strong>Project setup needed</strong><span>This project is not configured for self-service resources yet. Ask your platform administrator to finish project setup.</span></div>}
            {options.length > 0 && options.every((option) => !option.requestable) && <div className="notice-box muted"><strong>Provisioning is being prepared</strong><span>Approved options are listed below. Requests will open when a verified database runtime is available.</span></div>}
            {options.length === 0 && <div className="notice-box muted"><strong>Catalog unavailable</strong><span>The API did not return any resource options. Retry shortly or contact your platform team.</span></div>}
            <form onSubmit={submitRequest} className="request-form">
              <label>Database option<select value={form.option} onChange={(event) => setForm({ ...form, option: event.target.value })} disabled={!options.some((item) => item.requestable)} required><option value="">Select an approved option</option>{options.map((option) => <option key={optionKey(option)} value={optionKey(option)} disabled={!option.requestable}>{option.template_id} · PostgreSQL {option.version} · {option.size.id}{option.requestable ? "" : ` — ${option.unavailable_reason ?? "Not available"}`}</option>)}</select></label>
              {selectedOption && <div className="option-specs"><span><b>{selectedOption.size.cpu_millis / 1000}</b> vCPU</span><span><b>{formatBytes(selectedOption.size.memory_bytes)}</b> memory</span><span><b>{formatBytes(selectedOption.size.storage_bytes)}</b> storage</span></div>}
              <label>Resource name<input value={form.display_name} onChange={(event) => setForm({ ...form, display_name: event.target.value })} placeholder="e.g. checkout-feature-test" maxLength={100} required /></label>
              <label>Environment<select value={form.environment_id} onChange={(event) => setForm({ ...form, environment_id: event.target.value })} disabled={!project?.environments.length} required><option value="">Choose an environment</option>{project?.environments.map((environment) => <option key={environment.id} value={environment.id}>{environment.name}</option>)}</select></label>
              <label>Lifetime<select value={form.ttl_seconds} onChange={(event) => setForm({ ...form, ttl_seconds: Number(event.target.value) })} disabled={!selectedOption}><option value="">Choose a lifetime</option>{selectedOption && [...new Set([3600, 14400, 28800, 86400].filter((seconds) => seconds <= selectedOption.max_lifetime_seconds).concat(selectedOption.max_lifetime_seconds))].sort((a, b) => a - b).map((seconds) => <option key={seconds} value={seconds}>{formatDuration(seconds)}</option>)}</select><span className="field-hint">Maximum allowed: {selectedOption ? formatDuration(selectedOption.max_lifetime_seconds) : "—"}</span></label>
              <div className="form-footer"><span className="policy-note">Database and stored data are removed at expiry.</span><button className="primary-button" type="submit" disabled={!canRequest}>{busy ? "Working…" : "Request database →"}</button></div>
            </form>
          </section>

          <section className="panel resources-panel">
            <div className="panel-heading resources-heading"><div><div className="eyebrow">PROJECT ENVIRONMENTS</div><h2>Active resources <span className="count">{resources.length}</span></h2></div><button className="refresh-button" onClick={() => void refreshProject()} title="Refresh resources">↻</button></div>
          {catalogError && <div role="alert" className="failure-line">Resource catalog unavailable: {catalogError} <button type="button" onClick={() => void refreshProject()}>Retry</button></div>}
          {resources.length === 0 ? <div className="empty-state"><div className="empty-illustration"><span>▱</span><i /></div><strong>No resources yet</strong><p>When your team requests a development database, it will appear here with its status and expiry.</p></div> : <div className="resource-list">{resources.map((resource) => <ResourceCard key={resource.id} resource={resource} project={project} operation={operations[resource.id]} connection={connection?.resourceId === resource.id ? connection.value : null} canExtend={extensionChoices(resource).length > 0} onConnect={() => void revealConnection(resource)} onRenew={() => { setRenewing(resource); setRenewSeconds(extensionChoices(resource)[0] ?? 0); }} onDelete={() => void deleteResource(resource)} busy={busy || identityBusy} />)}</div>}
          {resourceAfter && <button className="secondary-button" type="button" onClick={() => void loadMoreResources()}>Load more resources</button>}
          </section>
        </div>}

        {(section === "applications" || section === "overview") && <><section className="panel applications-panel">
          <div className="panel-heading"><div><div className="eyebrow">APP STARTER</div><h2>Applications <span className="count">{applications.length}</span></h2></div></div>
          <form className="application-create" onSubmit={createApplication}>
            <label>Approved template<select value={appTemplate} onChange={(event) => setAppTemplate(event.target.value)} required>
              <option value="">Select a template</option>
              {appTemplates.map((item) => <option key={`${item.id}@${item.version}`} value={`${item.id}@${item.version}`}>{item.name} · {item.language} · v{item.version}</option>)}
            </select></label>
            <label>Environment<select value={appEnvironment} onChange={(event) => setAppEnvironment(event.target.value)} required><option value="">Choose an environment</option>{project?.environments.map((environment) => <option key={environment.id} value={environment.id}>{environment.name}</option>)}</select></label>
            <label>Application name<input value={appName} onChange={(event) => setAppName(event.target.value)} maxLength={64} placeholder="e.g. checkout-service" required /></label>
            <button className="primary-button" disabled={busy || identityBusy || !project?.configured || !appTemplates.length || !project.environments.length}>{busy ? "Working…" : "Create application →"}</button>
          </form>
          {applications.length === 0 ? <p className="applications-empty">Choose an approved template to start a project. Repository creation runs asynchronously and its progress is recorded below.</p> : <div className="application-list">{applications.map(({ application, steps }) => <article className="application-card" key={application.id}>
            <div className="application-heading"><div><Link href={`/dashboard/applications/${application.id}`}><strong>{application.name}</strong></Link><small>{application.template_id} · v{application.template_version} · {application.repository_url ?? "Repository pending"}</small></div><span className={`status status-${application.status}`}><i />{application.status}</span></div>
            <div className="delivery-steps">{steps.map((step) => <div className="delivery-step" key={step.id}><span className={`step-dot step-${step.status}`} /><span>{step.kind.replaceAll("_", " ")}</span><b>{step.status}</b><small>{step.attempts ? `attempt ${step.attempts}` : "queued"}{step.error_code ? ` · ${step.error_code}` : ""}</small>{step.status === "failed" && <button type="button" className="secondary-button" onClick={() => void retryDeliveryStep(application, step)} disabled={busy || identityBusy}>Retry step</button>}</div>)}</div>
          </article>)}</div>}
        </section>

        <section className="panel local-preview-panel">
          <div className="panel-heading"><div><div className="eyebrow">APPLICATION DELIVERY</div><h2>Register a local preview</h2></div><span className="catalog-icon">⌁</span></div>
          <p className="preview-intro">Applications can attach an approved local database and deploy an immutable image digest to the local target when supported. Preview addresses are for this machine only.</p>
          <form className="local-preview-form" onSubmit={registerLocalPreview}>
            <label>Preview name<input value={previewName} onChange={(event) => setPreviewName(event.target.value)} maxLength={64} required placeholder="e.g. checkout-preview" /></label>
            <label>Environment<select value={previewEnvironment} onChange={(event) => setPreviewEnvironment(event.target.value)} required><option value="">Choose an environment</option>{project?.environments.map((environment) => <option key={environment.id} value={environment.id}>{environment.name}</option>)}</select></label>
            <label>Lease<select value={previewTtl} onChange={(event) => setPreviewTtl(Number(event.target.value))}><option value={3600}>1 hour</option><option value={14400}>4 hours</option><option value={86400}>24 hours</option></select></label>
            <button className="primary-button" type="submit" disabled={busy || identityBusy || !project?.configured || !project.environments.length}>{busy ? "Registering…" : "Register local image →"}</button>
          </form>
          {localPreviews.length === 0 ? <p className="applications-empty">Applications and registered local previews appear here with their delivery history.</p> : <div className="application-list">{localPreviews.map((preview) => {
            const deployment = preview.deployments.at(-1);
            const resource = resources.find((item) => item.id === preview.application.resource_id);
            const deployed = deployment?.status === "succeeded" || deployment?.status === "ready";
            const attachmentStep = [...(preview.steps ?? [])].reverse().find((step) => step.kind === "resource");
            const attachmentPending = attachmentStep?.status === "pending" || attachmentStep?.status === "running";
            const waitingForDatabase = attachmentPending || (!!preview.application.resource_id && resource?.status !== "ready");
            return <article className="application-card" key={preview.application.id}>
              <div className="application-heading"><div><Link href={`/dashboard/applications/${preview.application.id}`}><strong>{preview.application.name}</strong></Link><small>{deployment?.image_digest ?? "Image digest required at deploy"} · {preview.application.template_id}</small></div><span className={`status status-${deployed ? "ready" : deployment?.status ?? "pending"}`}><i />{deployed ? "deployed" : deployment?.status ?? "registered"}</span></div>
              {historyErrors[preview.application.id] && <div className="failure-line" role="alert">Deployment history unavailable: {historyErrors[preview.application.id]} <button type="button" onClick={() => void refreshPreview(preview).catch((cause) => setHistoryErrors((current) => ({ ...current, [preview.application.id]: cause instanceof Error ? cause.message : "Could not reload history" })))}>Retry history</button></div>}
              <div className="preview-meta">{preview.application.expires_at && <span><small>EXPIRES</small><b>{formatDate(preview.application.expires_at)}</b></span>}<span><small>DATABASE</small><b>{!preview.application.resource_id ? "Not attached" : resource ? resource.status : "Attachment pending"}</b></span></div>
              {preview.steps?.some((step) => step.status === "failed") && <div className="failure-line" role="status">Deployment failed · {preview.steps.find((step) => step.status === "failed")?.error_code ?? "check delivery status"}. Retry deployment when ready.</div>}
              {deployed && deployment?.url && isLoopbackUrl(deployment.url) && <div className="preview-url"><strong>Local preview URL</strong><a href={deployment.url} target="_blank" rel="noreferrer">{deployment.url}</a><small>Loopback access on this machine only; this URL is not shareable.</small></div>}
              {deployed && deployment?.url && !isLoopbackUrl(deployment.url) && <div className="failure-line" role="status">Deployment succeeded, but the returned address is not a loopback URL and is hidden.</div>}
              <div className="preview-actions">
                {!preview.application.resource_id && <button className="secondary-button" onClick={() => void attachPreviewDatabase(preview)} disabled={!!previewBusyId || attachmentPending || !options.some((option) => option.target_id === "local" && option.requestable)}>{attachmentStep?.status === "failed" ? "Retry database attachment" : "Attach approved database"}</button>}
                {(preview.application.resource_id || attachmentStep) && <span className="field-hint">Database step: {attachmentPending ? "pending" : resource?.status ?? attachmentStep?.status ?? "pending"}{waitingForDatabase ? " — deployment waits for ready" : attachmentStep?.status === "failed" ? " — attachment failed; deploy without database or retry attachment" : " — ready"}</span>}
                <label className="preview-digest-field">Image digest for this deploy<input value={previewDigests[preview.application.id] ?? ""} onChange={(event) => setPreviewDigests((current) => ({ ...current, [preview.application.id]: event.target.value }))} placeholder="repo/image@sha256:… or sha256:<64 lowercase hex>" autoComplete="off" spellCheck={false} /><small>Use a registry digest or configured local Docker image ID (`sha256:` plus 64 lowercase hex characters). Mutable tags are not accepted.</small></label>
                <button className="primary-button" onClick={() => void deployLocalPreview(preview)} disabled={!!previewBusyId || deployed || waitingForDatabase || !previewDigests[preview.application.id]?.trim()}>{previewBusyId === preview.application.id ? "Working…" : deployed ? "Deployment complete" : deployment?.status === "failed" ? "Retry deployment" : attachmentStep?.status === "failed" ? "Deploy without database" : "Deploy locally"}</button>
              </div>
            </article>;
          })}</div>}
          {!options.some((option) => option.requestable && option.target_id === "local") && <p className="field-hint">No approved local PostgreSQL option is currently available. You can deploy a preview without a database.</p>}
        </section></>}

        {(section === "account" || section === "settings") && <IdentityAdministration
          key={`${principal.sessionId}:${project?.project_id ?? "no-project"}`}
          api={api}
          principal={principal}
          project={project}
          parentBusy={busy}
          mutationLock={identityMutationLock}
          isStaleRequest={isStaleApiRequest}
          getApiGeneration={currentApiGeneration}
          isApiGenerationCurrent={isCurrentGeneration}
          onSessionEnded={clearAuthentication}
          onIdentityChanged={loadSession}
          onMutationBusyChange={setIdentityBusy}
          section={section === "settings" ? "members" : "account"}
        />}

        {(section === "activity" || section === "overview") && <section className="panel activity-panel"><div className="panel-heading"><div><div className="eyebrow">AUDIT TRAIL</div><h2>{section === "overview" ? "Recent activity" : "Project activity"}</h2></div></div>{activityError ? <p role="alert">Activity unavailable: {activityError} <button type="button" onClick={() => void refreshProject()}>Retry</button></p> : activity.length ? <><div className="activity-list">{activity.slice(0, activityVisible).map((event) => <div className="activity-row" key={event.id}><span className="activity-marker" /><span className="activity-description"><strong>{event.action.replaceAll("_", " ")}</strong><small>by {event.actor_id ? event.actor_id.slice(0, 8) : "system"} · resource {event.resource_id.slice(0, 8)} · operation {operations[event.resource_id] ? `${operations[event.resource_id].action} · ${operations[event.resource_id].status}` : event.operation_id.slice(0, 8)}</small></span><time dateTime={event.created_at}>{formatDate(event.created_at)}</time></div>)}</div>{activityVisible < activity.length && <button className="secondary-button" type="button" onClick={() => setActivityVisible((count) => count + 10)}>Load more activity</button>}</> : <p className="identity-muted">No activity is available.</p>}</section>}

        <footer className="page-footer"><span>Resources are scoped to your project membership.</span>{error && <span role="status">API request needs attention</span>}</footer>
      </div>
    </section>

    {connection && <div className="modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setConnection(null); }}><section ref={dialogRef} className="modal" role="dialog" aria-modal="true" aria-labelledby="connection-title" tabIndex={-1}><button className="modal-close" onClick={() => setConnection(null)} aria-label="Close">×</button><span className="modal-icon">⌁</span><div className="eyebrow">SENSITIVE ACCESS</div><h2 id="connection-title">Database connection</h2><p>This connection string contains a password. It is shown only after your request and stays in this page’s memory. Close this window when finished.</p><div className="connection-facts"><span><small>HOST</small><b>{connection.details.host}</b></span><span><small>PORT</small><b>{connection.details.port}</b></span><span><small>DATABASE</small><b>{connection.details.database}</b></span><span><small>USER</small><b>{connection.details.user}</b></span></div><textarea readOnly value={connection.value} aria-label="Database connection string" onFocus={(event) => event.currentTarget.select()} /><p className="connection-instructions">{connection.details.instructions}</p><div className="modal-footer"><span>Access is recorded for security.</span><button className="secondary-button" onClick={() => void copyConnection()}>Copy connection</button><button className="primary-button" onClick={() => setConnection(null)}>Done</button></div></section></div>}
    {renewing && <div className="modal-backdrop"><section ref={dialogRef} className="modal" role="dialog" aria-modal="true" aria-labelledby="renew-title" tabIndex={-1}><button className="modal-close" onClick={() => setRenewing(null)} aria-label="Close">×</button><span className="modal-icon">◷</span><div className="eyebrow">RESOURCE LIFECYCLE</div><h2 id="renew-title">Extend lease</h2><p>Choose an expiry measured from the database creation time. It must stay within the catalog lifetime limit.</p><form onSubmit={renewResource}><label>Total lease<select value={renewSeconds} onChange={(event) => setRenewSeconds(Number(event.target.value))} disabled={!extensionChoices(renewing).length || busy}>{extensionChoices(renewing).map((seconds) => <option key={seconds} value={seconds}>{formatLeaseDuration(seconds)}</option>)}</select></label>{extensionChoices(renewing).length ? <p className="field-hint">New expiry: {formatDate(new Date(Date.parse(renewing.created_at) + renewSeconds * 1000).toISOString())}</p> : <p className="field-hint">This resource has reached its maximum permitted lifetime.</p>}<div className="modal-footer"><button className="secondary-button" type="button" onClick={() => setRenewing(null)}>Cancel</button><button className="primary-button" type="submit" disabled={busy || identityBusy || !extensionChoices(renewing).includes(renewSeconds)}>{busy ? "Saving…" : "Update lease"}</button></div></form></section></div>}
  </main>;
}

function optionKey(option: Option) { return `${option.template_id}:${option.version}:${option.target_id}:${option.size.id}`; }

function isLoopbackUrl(value: string) {
  try { const url = new URL(value); return ["http:", "https:"].includes(url.protocol) && !url.username && !url.password && ["localhost", "127.0.0.1", "[::1]", "::1"].includes(url.hostname); }
  catch { return false; }
}

function leaseExtensionChoices(resource: Resource, options: Option[]) {
  const matching = options.filter((option) => option.template_id === resource.template_id && option.target_id === resource.target_id && option.size.id === resource.size_id);
  const maxLifetime = matching.reduce((maximum, option) => Math.max(maximum, option.max_lifetime_seconds), 0);
  const created = Date.parse(resource.created_at);
  const currentExpiry = Date.parse(resource.expires_at);
  if (!maxLifetime || Number.isNaN(created) || Number.isNaN(currentExpiry)) return [];
  return [7200, 14400, 28800, 43200, 86400].filter((seconds) => {
    const expiresAt = created + seconds * 1000;
    return seconds <= maxLifetime && expiresAt > currentExpiry && expiresAt > Date.now();
  });
}

function formatLeaseDuration(seconds: number) {
  return seconds % 3600 === 0 ? `${seconds / 3600} hours total` : `${seconds / 60} minutes total`;
}

function ResourceCard({ resource, project, operation, connection, canExtend, onConnect, onRenew, onDelete, busy }: { resource: Resource; project: Project | null; operation?: Operation; connection: string | null; canExtend: boolean; onConnect: () => void; onRenew: () => void; onDelete: () => void; busy: boolean }) {
  const environment = project?.environments.find((item) => item.id === resource.environment_id)?.name ?? "Environment";
  const status = resource.status.toLowerCase().replaceAll("_", " ");
  const ready = resource.status === "ready" && resource.desired_state !== "deleted";
  const deleting = resource.status === "deleting";
  return <article className="resource-card"><div className="resource-card-top"><div className="db-icon">▤</div><div className="resource-title"><Link href={`/dashboard/resources/${resource.id}`}><strong>{resource.display_name}</strong></Link><span>{resource.template_id.replaceAll("_", " ")} · {resource.target_id} · {resource.size_id}</span></div><span className={`status status-${resource.status}`}><i />{status}</span></div>
    <div className="resource-meta"><span><small>ENVIRONMENT</small><b>{environment}</b></span><span><small>EXPIRES</small><b>{formatDate(resource.expires_at)}</b></span><span><small>RESOURCE ID</small><b className="mono">{resource.id.slice(0, 8)}</b></span></div>
    {operation && <div className={`operation-line operation-${operation.status}`}><span className="operation-spinner" />{operation.action} operation {operation.status}{operation.error_code ? ` · ${operation.error_code}` : ""} · attempt {operation.attempts}</div>}
    {resource.failure_code && <div className="failure-line" role="status">Cleanup or provisioning needs attention · {resource.failure_code}. Resource remains tracked for retry.</div>}
    {connection && <div className="inline-connection"><span>Connection available in the secure dialog</span><button onClick={onConnect} disabled={busy}>Show again</button></div>}
    <div className="resource-actions"><button onClick={onConnect} disabled={!ready || busy} title={!ready ? "Available when the database is ready" : "Retrieve connection details"}>⌁ <span>Connect</span></button><button onClick={onRenew} disabled={!ready || busy || !canExtend} title={!canExtend ? "Maximum permitted lifetime reached" : "Extend the lease within its catalog limit"}>◷ <span>Extend</span></button><button className="delete-action" onClick={onDelete} disabled={deleting || busy}>⌫ <span>{deleting ? "Deletion tracked" : resource.status === "cleanup_failed" ? "Retry cleanup" : "Delete"}</span></button></div>
  </article>;
}

function Login({ visitAsGuest, username, password, setUsername, setPassword, submit, error, busy }: { visitAsGuest: () => void; username: string; password: string; setUsername: (value: string) => void; setPassword: (value: string) => void; submit: (event: FormEvent<HTMLFormElement>) => void; error: string; busy: boolean }) {
  return <main className="login-screen"><div className="login-decoration decor-one" /><div className="login-decoration decor-two" /><section className="login-card"><div className="brand login-brand"><span className="brand-mark">D</span><span>devops<span className="brand-light">hub</span></span></div><div className="login-overline">INTERNAL DEVELOPER PLATFORM</div><h1>Build with confidence.</h1><p className="login-intro">Sign in to provision and manage your team’s development resources.</p>{error && <div role="alert" className="login-error">{error}</div>}<form onSubmit={submit} className="login-form"><label htmlFor="username">Username<input id="username" autoComplete="username" value={username} onChange={(event) => setUsername(event.target.value)} required /></label><label htmlFor="password">Password<input id="password" type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} required /></label><button className="primary-button login-button" disabled={busy}>{busy ? "Signing in…" : "Sign in"}<span>→</span></button></form><button type="button" className="secondary-button login-button" onClick={visitAsGuest} disabled={busy}>Visit as guest →</button><div className="login-security"><span>◈</span> Company managed access <i /> Secure session</div></section><p className="login-footnote">Need access? Contact your platform administrator.</p></main>;
}
