"use client";

import { FormEvent, useEffect, useRef, useState } from "react";

type ApiCall = <T>(path: string, init?: RequestInit) => Promise<T>;
type Principal = {
  userId: string;
  sessionId: string;
  role?: string | null;
  memberships: { projectId: string; projectName: string; role: string }[];
};
type Project = { project_id: string; name: string } | null;
type BrowserSession = {
  sessionId: string;
  createdAt: string;
  lastSeenAt: string;
  idleExpiresAt: string;
  absoluteExpiresAt: string;
  current: boolean;
};
type ProjectMember = { userId: string; userName: string; role: "admin" | "developer"; active: boolean };

export default function IdentityAdministration({
  api,
  principal,
  project,
  parentBusy,
  mutationLock,
  isStaleRequest,
  getApiGeneration,
  isApiGenerationCurrent,
  onSessionEnded,
  onIdentityChanged,
  onMutationBusyChange,
}: {
  api: ApiCall;
  principal: Principal;
  project: Project;
  parentBusy: boolean;
  mutationLock: { current: symbol | null };
  isStaleRequest: (cause: unknown) => boolean;
  getApiGeneration: () => number;
  isApiGenerationCurrent: (generation: number) => boolean;
  onSessionEnded: (message?: string) => void;
  onIdentityChanged: () => Promise<void>;
  onMutationBusyChange: (busy: boolean) => void;
}) {
  const [sessions, setSessions] = useState<BrowserSession[]>([]);
  const [members, setMembers] = useState<ProjectMember[]>([]);
  const [sessionLoading, setSessionLoading] = useState(true);
  const [membersLoading, setMembersLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [existingUserId, setExistingUserId] = useState("");
  const [newMemberRole, setNewMemberRole] = useState<"admin" | "developer">("developer");
  const mounted = useRef(true);
  const sessionsLoad = useRef(0);
  const membersLoad = useRef(0);
  const currentRole = project
    ? principal.memberships.find((membership) => membership.projectId === project.project_id)?.role ?? principal.role
    : null;
  const isProjectAdmin = currentRole === "admin";
  const controlsDisabled = busy || parentBusy || mutationLock.current !== null;

  function beginMutation() {
    if (parentBusy || mutationLock.current !== null) return null;
    const owner = Symbol("identity-mutation");
    mutationLock.current = owner;
    onMutationBusyChange(true);
    setBusy(true);
    return owner;
  }

  function endMutation(owner: symbol) {
    if (mutationLock.current !== owner) return;
    mutationLock.current = null;
    onMutationBusyChange(false);
    setBusy(false);
  }

  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);

  useEffect(() => {
    let active = true;
    let stale = false;
    const generation = getApiGeneration();
    const sequence = ++sessionsLoad.current;
    setSessionLoading(true);
    setError("");
    void api<BrowserSession[]>("me/sessions")
      .then((rows) => {
        if (!isApiGenerationCurrent(generation)) { stale = true; return; }
        if (active && sessionsLoad.current === sequence) setSessions(rows);
      })
      .catch((cause: unknown) => {
        if (isStaleRequest(cause) || !isApiGenerationCurrent(generation)) { stale = true; return; }
        if (active && sessionsLoad.current === sequence) setError(messageOf(cause, "Could not load active sessions"));
      })
      .finally(() => { if (active && sessionsLoad.current === sequence && !stale && isApiGenerationCurrent(generation)) setSessionLoading(false); });
    return () => { active = false; };
  }, [api, principal.sessionId, getApiGeneration, isApiGenerationCurrent, isStaleRequest]);

  useEffect(() => {
    if (!project || !isProjectAdmin) {
      setMembers([]);
      setMembersLoading(false);
      return;
    }
    let active = true;
    let stale = false;
    const generation = getApiGeneration();
    const sequence = ++membersLoad.current;
    setMembersLoading(true);
    void api<ProjectMember[]>(`projects/${project.project_id}/members`)
      .then((rows) => {
        if (!isApiGenerationCurrent(generation)) { stale = true; return; }
        if (active && membersLoad.current === sequence) setMembers(rows);
      })
      .catch((cause: unknown) => {
        if (isStaleRequest(cause) || !isApiGenerationCurrent(generation)) { stale = true; return; }
        if (active && membersLoad.current === sequence) setError(messageOf(cause, "Could not load project members"));
      })
      .finally(() => { if (active && membersLoad.current === sequence && !stale && isApiGenerationCurrent(generation)) setMembersLoading(false); });
    return () => { active = false; };
  }, [api, project?.project_id, isProjectAdmin, getApiGeneration, isApiGenerationCurrent, isStaleRequest]);

  async function reloadSessions(): Promise<boolean> {
    const generation = getApiGeneration();
    let rows: BrowserSession[];
    try { rows = await api<BrowserSession[]>("me/sessions"); }
    catch (cause) {
      if (!isApiGenerationCurrent(generation) || isStaleRequest(cause)) return false;
      throw cause;
    }
    if (!isApiGenerationCurrent(generation)) return false;
    setSessions(rows);
    return true;
  }

  async function reloadMembers(): Promise<boolean> {
    if (!project) return false;
    const generation = getApiGeneration();
    let rows: ProjectMember[];
    try { rows = await api<ProjectMember[]>(`projects/${project.project_id}/members`); }
    catch (cause) {
      if (!isApiGenerationCurrent(generation) || isStaleRequest(cause)) return false;
      throw cause;
    }
    if (!isApiGenerationCurrent(generation)) return false;
    if (mounted.current) setMembers(rows);
    return true;
  }

  async function revokeSession(session: BrowserSession) {
    const current = session.current || session.sessionId === principal.sessionId;
    const accepted = window.confirm(current
      ? "End your current session? You will need to sign in again."
      : "Revoke this browser session? The device will need to sign in again.");
    if (!accepted) return;
    const generation = getApiGeneration();
    const owner = beginMutation(); if (!owner) return;
    setError(""); setNotice("");
    try {
      await api(`me/sessions/${encodeURIComponent(session.sessionId)}`, { method: "DELETE" });
      if (!isApiGenerationCurrent(generation)) return;
      if (current) onSessionEnded("Your session was ended. Sign in again to continue.");
      else { const updated = await reloadSessions(); if (updated && isApiGenerationCurrent(generation)) setNotice("Session revoked."); }
    } catch (cause) { if (!isStaleRequest(cause) && isApiGenerationCurrent(generation)) setError(messageOf(cause, "Could not revoke the session")); }
    finally { endMutation(owner); }
  }

  async function revokeAllSessions() {
    if (parentBusy || mutationLock.current !== null || !window.confirm("Sign out every active session, including this one? You will need to sign in again.")) return;
    const owner = beginMutation(); if (!owner) return;
    const generation = getApiGeneration();
    setError(""); setNotice("");
    try {
      await api("auth/logout-all", { method: "POST", body: "{}" });
      if (!isApiGenerationCurrent(generation)) return;
      onSessionEnded("All sessions were signed out. Sign in again to continue.");
    } catch (cause) { if (!isStaleRequest(cause) && isApiGenerationCurrent(generation)) setError(messageOf(cause, "Could not sign out all sessions")); }
    finally { endMutation(owner); }
  }

  async function changePassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(""); setNotice("");
    if (newPassword.length < 12) { setError("Choose a new password with at least 12 characters."); setCurrentPassword(""); setNewPassword(""); setConfirmPassword(""); return; }
    if (newPassword !== confirmPassword) { setError("The new password and confirmation do not match."); setCurrentPassword(""); setNewPassword(""); setConfirmPassword(""); return; }
    const owner = beginMutation();
    if (!owner) { setCurrentPassword(""); setNewPassword(""); setConfirmPassword(""); return; }
    const generation = getApiGeneration();
    try {
      await api("me/password", { method: "POST", body: JSON.stringify({ currentPassword, newPassword }) });
      if (!isApiGenerationCurrent(generation)) return;
      setCurrentPassword(""); setNewPassword(""); setConfirmPassword("");
      onSessionEnded("Password changed. All sessions were ended; sign in with your new password.");
    } catch (cause) { if (!isStaleRequest(cause) && isApiGenerationCurrent(generation)) setError(messageOf(cause, "Could not change password")); }
    finally {
      setCurrentPassword(""); setNewPassword(""); setConfirmPassword(""); endMutation(owner);
    }
  }

  async function updateMemberRole(member: ProjectMember, role: "admin" | "developer") {
    if (!project || role === member.role) return;
    const owner = beginMutation(); if (!owner) return;
    const generation = getApiGeneration();
    setError(""); setNotice("");
    try {
      await api(`projects/${project.project_id}/members/${encodeURIComponent(member.userId)}`, {
        method: "PUT", body: JSON.stringify({ role }),
      });
      if (!isApiGenerationCurrent(generation)) return;
      if (!mounted.current) return;
      const [memberResult] = await Promise.allSettled([reloadMembers(), onIdentityChanged()]);
      if (!isApiGenerationCurrent(generation)) return;
      if (!mounted.current) return;
      if (memberResult.status === "rejected") throw memberResult.reason;
      setNotice(`Updated ${member.userName}'s project role.`);
    } catch (cause) { if (!isStaleRequest(cause) && isApiGenerationCurrent(generation)) setError(messageOf(cause, "Could not update project role")); }
    finally { endMutation(owner); }
  }

  async function removeMember(member: ProjectMember) {
    if (!project || !window.confirm(`Remove ${member.userName} from ${project.name}? Their access to this project will end.`)) return;
    const owner = beginMutation(); if (!owner) return;
    const generation = getApiGeneration();
    setError(""); setNotice("");
    try {
      await api(`projects/${project.project_id}/members/${encodeURIComponent(member.userId)}`, { method: "DELETE" });
      if (!isApiGenerationCurrent(generation)) return;
      if (!mounted.current) return;
      const [memberResult] = await Promise.allSettled([reloadMembers(), onIdentityChanged()]);
      if (!isApiGenerationCurrent(generation)) return;
      if (!mounted.current) return;
      if (memberResult.status === "rejected") throw memberResult.reason;
      setNotice(`Removed ${member.userName} from the project.`);
    } catch (cause) { if (!isStaleRequest(cause) && isApiGenerationCurrent(generation)) setError(messageOf(cause, "Could not remove project member")); }
    finally { endMutation(owner); }
  }

  async function addExistingMember(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!project) return;
    const userId = existingUserId.trim();
    if (!isUuid(userId)) { setError("Enter the UUID of an existing internal user."); return; }
    const owner = beginMutation(); if (!owner) return;
    const generation = getApiGeneration();
    setError(""); setNotice("");
    try {
      await api(`projects/${project.project_id}/members/${encodeURIComponent(userId)}`, {
        method: "PUT", body: JSON.stringify({ role: newMemberRole }),
      });
      if (!isApiGenerationCurrent(generation)) return;
      if (!mounted.current) return;
      setExistingUserId("");
      const [memberResult] = await Promise.allSettled([reloadMembers(), onIdentityChanged()]);
      if (!isApiGenerationCurrent(generation)) return;
      if (!mounted.current) return;
      if (memberResult.status === "rejected") throw memberResult.reason;
      setNotice("Existing user added to the project.");
    } catch (cause) { if (!isStaleRequest(cause) && isApiGenerationCurrent(generation)) setError(messageOf(cause, "Could not add project member")); }
    finally { endMutation(owner); }
  }

  return <section className="panel identity-panel" aria-labelledby="identity-heading">
    <div className="panel-heading"><div><div className="eyebrow">ACCOUNT & ACCESS</div><h2 id="identity-heading">Identity administration</h2></div></div>
    {(error || notice) && <div className={`identity-message ${error ? "identity-error" : "identity-success"}`} role={error ? "alert" : "status"}>{error || notice}</div>}
    <div className="identity-columns">
      <div className="identity-column">
        <div className="identity-subheading"><div><h3>Active sessions</h3><p>Review devices that can access your account.</p></div><button className="secondary-button" type="button" onClick={() => void reloadSessions().catch((cause: unknown) => { if (!isStaleRequest(cause)) setError(messageOf(cause, "Could not refresh sessions")); })} disabled={parentBusy}>Refresh</button></div>
        {sessionLoading ? <p className="identity-muted">Loading sessions…</p> : sessions.length === 0 ? <p className="identity-muted">No active sessions were returned.</p> : <div className="identity-session-list">{sessions.map((session) => {
          const current = session.current || session.sessionId === principal.sessionId;
          return <article className="identity-session" key={session.sessionId}>
            <div><strong>{current ? "This session" : `Session · ${session.sessionId.slice(0, 8)}`}</strong><span>Last used {formatDate(session.lastSeenAt)}</span><small>Idle expiry {formatDate(session.idleExpiresAt)} · Absolute expiry {formatDate(session.absoluteExpiresAt)}</small></div>
            <button className="identity-danger-button" type="button" onClick={() => void revokeSession(session)} disabled={controlsDisabled}>{current ? "End session" : "Revoke"}</button>
          </article>;
        })}</div>}
        <button className="identity-danger-button identity-revoke-all" type="button" onClick={() => void revokeAllSessions()} disabled={controlsDisabled || sessions.length === 0}>{busy ? "Working…" : "Sign out all sessions"}</button>

        <form className="identity-password-form" onSubmit={changePassword}>
          <div className="identity-subheading"><div><h3>Change password</h3><p>Changing it signs out every active session, including this one.</p></div></div>
          <label>Current password<input type="password" autoComplete="current-password" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} required disabled={controlsDisabled} /></label>
          <label>New password<input type="password" autoComplete="new-password" minLength={12} value={newPassword} onChange={(event) => setNewPassword(event.target.value)} required disabled={controlsDisabled} /><small>Use at least 12 characters.</small></label>
          <label>Confirm new password<input type="password" autoComplete="new-password" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} required disabled={controlsDisabled} /></label>
          <button className="primary-button" type="submit" disabled={controlsDisabled || !currentPassword || !newPassword || !confirmPassword}>{busy ? "Updating…" : "Change password"}</button>
        </form>
      </div>

      <div className="identity-column">
        <div className="identity-subheading"><div><h3>Project members</h3><p>{project ? `Manage access to ${project.name}.` : "Select a project to manage its membership."}</p></div></div>
        {!project ? <p className="identity-muted">No project is selected.</p> : !isProjectAdmin ? <p className="identity-muted">Project administrators can view and change membership. Your project role is {currentRole ?? "developer"}.</p> : <>
          {membersLoading ? <p className="identity-muted">Loading project members…</p> : members.length === 0 ? <p className="identity-muted">No project members were returned.</p> : <div className="identity-member-list">{members.map((member) => <article className="identity-member" key={member.userId}>
            <div className="identity-member-name"><strong>{member.userName}</strong><small>{member.userId}</small>{!member.active && <em>Inactive</em>}</div>
            <select aria-label={`Role for ${member.userName}`} value={member.role} disabled={controlsDisabled || !member.active} onChange={(event) => void updateMemberRole(member, event.target.value as "admin" | "developer")}><option value="developer">Developer</option><option value="admin">Admin</option></select>
            <button className="identity-danger-button" type="button" onClick={() => void removeMember(member)} disabled={controlsDisabled || !member.active}>Remove</button>
          </article>)}</div>}
          <form className="identity-add-form" onSubmit={addExistingMember}>
            <h4>Add an existing internal user</h4>
            <p>Users are created by an operator. Enter an existing account UUID; this does not create an account.</p>
            <label>User UUID<input value={existingUserId} onChange={(event) => setExistingUserId(event.target.value)} placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" autoComplete="off" spellCheck={false} disabled={controlsDisabled} required /></label>
            <label>Project role<select value={newMemberRole} onChange={(event) => setNewMemberRole(event.target.value as "admin" | "developer")} disabled={controlsDisabled}><option value="developer">Developer</option><option value="admin">Admin</option></select></label>
            <button className="primary-button" type="submit" disabled={controlsDisabled || !existingUserId.trim()}>{busy ? "Saving…" : "Add existing user"}</button>
          </form>
        </>}
      </div>
    </div>
  </section>;
}

function messageOf(cause: unknown, fallback: string) {
  return cause instanceof Error && cause.message ? cause.message : fallback;
}

function formatDate(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "unknown" : new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date);
}

function isUuid(value: string) {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value);
}
