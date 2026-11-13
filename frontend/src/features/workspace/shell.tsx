"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { useWorkspace } from "./session";
const links = [["overview", "Overview"], ["resources", "Resources"], ["applications", "Applications"], ["account", "Account"], ["settings", "Project settings"], ["activity", "Activity"]] as const;
export function WorkspaceShell({ children }: {
    children: React.ReactNode;
}) {
    const { principal, projects, project, loading, transitioning, error, selectProject, signOut, refresh } = useWorkspace();
    const pathname = usePathname();
    const router = useRouter();
    useEffect(() => {
        if (!loading && !principal && (!error || error.startsWith("Your session ended")))
            router.replace(`/login?next=${encodeURIComponent(`${pathname}${window.location.search}`)}`);
    }, [loading, principal, error, pathname, router]);
    if (loading)
        return <main className="center-screen"><p role="status">Checking your session…</p></main>;
    if (!principal)
        return <main className="center-screen"><section className="panel"><h1>{error ? "Workspace unavailable" : "Redirecting to sign in"}</h1>{error ? <><p role="alert">{error}</p><button className="primary-button" onClick={() => void refresh()}>Retry</button></> : <p role="status">Checking your session…</p>}</section></main>;
    const active = pathname === "/dashboard" || pathname === "/dashboard/overview" ? "overview" : pathname.split("/")[2];
    return <><a className="skip-link" href="#workspace-content">Skip to main content</a><div className="shell"><aside className="sidebar"><Link className="brand" href="/"><span className="brand-mark">D</span><span>devops<span className="brand-light">hub</span></span></Link><div className="workspace-label">WORKSPACE</div><label className="project-select-label" htmlFor="project-select">Project</label><select id="project-select" disabled={transitioning} className="project-select" value={project?.project_id ?? ""} onChange={e => void selectProject(e.target.value)}>{projects.map(p => <option key={p.project_id} value={p.project_id}>{p.name}</option>)}</select><nav className="nav" aria-label="Workspace">{links.map(([id, label]) => <Link key={id} className={`nav-item ${active === id ? "active" : ""}`} aria-current={active === id ? "page" : undefined} href={id === "overview" ? "/dashboard" : `/dashboard/${id}`}>{label}</Link>)}</nav><div className="sidebar-bottom"><Link href="/dashboard/account" className="avatar" aria-label="Account">{principal.userName[0]?.toUpperCase()}</Link><div className="user-copy"><strong>{principal.userName}</strong><span>{project?.name ?? "No project"}</span></div><button className="icon-button" disabled={transitioning} onClick={() => void signOut()} aria-label="Sign out">↪</button></div></aside><main id="workspace-content" className="main-content" tabIndex={-1}><header className="topbar"><div className="breadcrumb">Workspace <span>/</span> {active}</div><div className="topbar-right"><span className="secure-label">{project?.name ?? "No project selected"}</span></div></header>{error && <div className="alert error" role="alert">{error}</div>}<div key={`${principal.sessionId}:${project?.project_id ?? "no-project"}`}>{transitioning ? <p role="status" className="content-wrap">Updating workspace session…</p> : children}</div></main></div></>;
}
