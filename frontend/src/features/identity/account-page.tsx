"use client";
import { useRef } from "react";
import IdentityAdministration from "./administration";
import { api, apiGeneration, isApiGenerationCurrent, isStaleRequest } from "@/lib/api/client";
import { useWorkspace } from "@/features/workspace/session";
export function AccountPage({ members = false }: {
    members?: boolean;
}) {
    const { principal, project, refresh } = useWorkspace();
    const lock = useRef<symbol | null>(null);
    const onBusyChange = () => { };
    if (!principal)
        return null;
    return <div className="content-wrap"><header className="page-heading"><div><div className="eyebrow">DEVELOPER PLATFORM</div><h1>{members ? "Project settings" : "Account security"}</h1><p>{members ? "Manage membership for the selected project." : "Manage your identity security and active sessions."}</p></div></header><IdentityAdministration key={`${principal.sessionId}:${project?.project_id ?? "none"}`} api={api} principal={principal} project={project} parentBusy={false} mutationLock={lock} isStaleRequest={isStaleRequest} getApiGeneration={apiGeneration} isApiGenerationCurrent={isApiGenerationCurrent} onSessionEnded={message => { void message; const next = `${window.location.pathname}${window.location.search}`; window.location.assign(`/login?next=${encodeURIComponent(next)}`); }} onIdentityChanged={refresh} onMutationBusyChange={onBusyChange} section={members ? "members" : "account"}/></div>;
}
