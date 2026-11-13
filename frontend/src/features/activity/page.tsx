"use client";
import { useActivity } from "./use-activity";
import { useWorkspace } from "@/features/workspace/session";
export function ActivityPage() {
    const { items, error, loading, visible, setVisible, refresh } = useActivity();
    const { project } = useWorkspace();
    return <div className="content-wrap"><header className="page-heading"><div><div className="eyebrow">DEVELOPER PLATFORM</div><h1>Project activity</h1><p>Recent operations recorded for {project?.name ?? "this project"}.</p></div></header><section className="panel activity-panel"><div className="panel-heading"><h2>Activity</h2><button className="refresh-button" onClick={() => void refresh()} aria-label="Refresh activity">↻</button></div>
    {loading ? <p role="status">Loading activity…</p> : error ? <p role="alert">{error} <button onClick={() => void refresh()}>Retry</button></p> : items.length ? <><div className="activity-list">{items.slice(0, visible).map(item => <article className="activity-row" key={item.id}><span className="activity-marker"/><span className="activity-description"><strong>{item.action.replaceAll("_", " ")}</strong><small>by {item.actor_id?.slice(0, 8) ?? "system"} · resource {item.resource_id.slice(0, 8)} · operation {item.operation_id.slice(0, 8)}</small></span><time dateTime={item.created_at}>{new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(item.created_at))}</time></article>)}</div>{visible < items.length && <button className="secondary-button" onClick={() => setVisible(value => value + 10)}>Load more activity</button>}</> : <p className="identity-muted">No activity is available.</p>}
  </section></div>;
}
