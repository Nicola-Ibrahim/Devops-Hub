import { notFound } from "next/navigation";
import { ApplicationDetail } from "@/features/applications/detail";
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
export default async function Page({ params }: {
    params: Promise<{
        applicationId: string;
    }>;
}) {
    const { applicationId } = await params;
    if (!uuid.test(applicationId))
        notFound();
    return <ApplicationDetail id={applicationId}/>;
}
