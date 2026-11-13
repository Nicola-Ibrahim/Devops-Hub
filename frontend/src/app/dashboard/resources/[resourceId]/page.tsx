import { notFound } from "next/navigation";
import { ResourceDetail } from "@/features/resources/detail";
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
export default async function Page({ params }: {
    params: Promise<{
        resourceId: string;
    }>;
}) {
    const { resourceId } = await params;
    if (!uuid.test(resourceId))
        notFound();
    return <ResourceDetail id={resourceId}/>;
}
