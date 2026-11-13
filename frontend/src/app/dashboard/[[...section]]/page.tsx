import Dashboard from "@/components/dashboard";
import { notFound } from "next/navigation";
import EntityDetail from "@/components/entity-detail";

const sections = ["overview", "resources", "applications", "account", "settings", "activity"] as const;
export default async function WorkspacePage({ params }: { params: Promise<{ section?: string[] }> }) {
  const { section } = await params;
  const selected = section?.[0] ?? "overview";
  if (section?.length === 2 && (selected === "resources" || selected === "applications")) {
    if (!/^[a-f0-9-]{36}$/i.test(section[1])) notFound();
    return <EntityDetail kind={selected} id={section[1]} />;
  }
  if ((section?.length ?? 0) > 1 || !sections.includes(selected as typeof sections[number])) notFound();
  return <Dashboard section={selected as typeof sections[number]} />;
}
