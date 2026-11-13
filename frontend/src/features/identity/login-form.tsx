"use client";
import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { api, beginSessionTransition, setSession, setActiveProject } from "@/lib/api/client";
import type { BrowserEnvelope } from "@/features/identity/types";
import type { Project } from "@/features/workspace/types";
function safeNext(value: string | null) { return value && /^\/dashboard(?:\/(?:overview|resources|applications|account|settings|activity)|\/(?:resources|applications)\/[a-f0-9-]{36})?(?:\?.*)?$/i.test(value) ? value : "/dashboard"; }
export default function LoginForm() {
    const [username, setUsername] = useState("");
    const [password, setPassword] = useState("");
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState("");
    const router = useRouter();
    const search = useSearchParams();
    useEffect(() => {
        let active = true;
        void api<BrowserEnvelope>("me/browser").then(() => {
            if (active)
                router.replace(safeNext(search.get("next")));
        }).catch(() => { });
        return () => { active = false; };
    }, [router, search]);
    async function submit(e: FormEvent) {
        e.preventDefault();
        setBusy(true);
        setError("");
        beginSessionTransition();
        try {
            const envelope = await api<BrowserEnvelope>("auth/login", { method: "POST", body: JSON.stringify({ userName: username, password }) });
            setSession(envelope);
            const projects = await api<Project[]>("projects");
            const selected = projects.find(p => p.project_id === envelope.principal.projectId) ?? projects[0] ?? null;
            setActiveProject(selected?.project_id ?? null);
            if (selected && selected.project_id !== envelope.principal.projectId) {
                const switched = await api<BrowserEnvelope>("auth/project", { method: "POST", body: JSON.stringify({ projectId: selected.project_id }) });
                setSession(switched);
            }
            router.replace(safeNext(search.get("next")));
            router.refresh();
        }
        catch (cause) {
            setError(cause instanceof Error ? cause.message : "Sign in failed");
        }
        finally {
            setPassword("");
            setBusy(false);
        }
    }
    return <main className="login-screen"><section className="login-card"><Link className="brand login-brand" href="/">devops<span className="brand-light">hub</span></Link><div className="login-overline">INTERNAL DEVELOPER PLATFORM</div><h1>Sign in</h1><p className="login-intro">Use your company account to access approved project resources.</p>{error && <p role="alert" className="login-error">{error}</p>}<form onSubmit={submit} className="login-form"><label htmlFor="username">Username<input id="username" autoComplete="username" value={username} onChange={e => setUsername(e.target.value)} required/></label><label htmlFor="password">Password<input id="password" type="password" autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)} required/></label><button className="primary-button login-button" disabled={busy}>{busy ? "Signing in…" : "Sign in →"}</button></form><Link className="secondary-button login-button" href="/demo">Visit as guest →</Link><p className="login-footnote">Need access? Contact your platform administrator.</p></section></main>;
}
