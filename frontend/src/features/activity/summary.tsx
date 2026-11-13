"use client";
import Link from "next/link";
import { useActivity } from "./use-activity";
export function ActivitySummary() {
    const { items, error, loading, refresh } = useActivity();
    return <section className="panel">
    <div className="panel-heading"><h2>Recent activity</h2><Link href="/dashboard/activity">View activity →</Link></div>
    {loading && items.length === 0 ? <p role="status">Loading activity…</p> : error ? <p role="alert">Activity unavailable. <button className="secondary-button" onClick={() => void refresh()}>Retry</button></p> : items.length === 0 ? <p className="identity-muted">No recent activity in this project.</p> : <div className="activity-list">{items.slice(0, 5).map(item => <div className="activity-row" key={item.id}><span className="activity-marker"/><span className="activity-description"><strong>{item.action.replaceAll("_", " ")}</strong><small>Resource {item.resource_id.slice(0, 8)} · Operation {item.operation_id.slice(0, 8)}</small></span><time dateTime={item.created_at}>{new Date(item.created_at).toLocaleString()}</time></div>)}</div>}
  </section>;
}
