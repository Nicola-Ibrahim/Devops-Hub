import Link from "next/link";
import { ResourceSummary } from "@/features/resources/summary";
import { ActivitySummary } from "@/features/activity/summary";
export default function OverviewPage() {
    return <div className="content-wrap">
    <header className="page-heading"><div><div className="eyebrow">DEVELOPER PLATFORM</div><h1>Workspace overview</h1><p>Review development resources, upcoming expiry and recent operations.</p></div><Link className="secondary-button" href="/dashboard/applications">View applications →</Link></header>
    <ResourceSummary />
    <ActivitySummary />
  </div>;
}
