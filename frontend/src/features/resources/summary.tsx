"use client";
import Link from "next/link";
import { useResources } from "./use-resources";
export function ResourceSummary() {
    const { resources, loading, resourceError, refresh } = useResources();
    if (loading && resources.length === 0)
        return <p role="status">Loading resource summary…</p>;
    if (resourceError)
        return <div className="alert error" role="alert">Resource summary unavailable. <button onClick={() => void refresh()}>Retry</button></div>;
    const now = Date.now();
    const expiring = resources.filter(resource => {
        const expiry = Date.parse(resource.expires_at);
        return resource.desired_state !== "deleted" && !["expired", "deleted"].includes(resource.status) && expiry > now && expiry <= now + 3600000;
    });
    const failed = resources.filter(resource => resource.status.includes("failed"));
    return <section aria-label="Resource summary">
    <div className="dashboard-stats">
      <article className="panel"><strong>{resources.length}</strong><span>Loaded resources</span><Link href="/dashboard/resources">View resources →</Link></article>
      <article className="panel"><strong>{expiring.length}</strong><span>Expire within one hour</span><Link href="/dashboard/resources">Review leases →</Link></article>
      <article className="panel"><strong>{failed.length}</strong><span>Need attention</span><Link href="/dashboard/resources">Review failures →</Link></article>
    </div>
    <p className="field-hint">Summary covers the first loaded page of resources in the selected project.</p>
  </section>;
}
