import { WorkspaceProvider } from "@/features/workspace/session";
import { WorkspaceShell } from "@/features/workspace/shell";
export default function DashboardLayout({ children }: {
    children: React.ReactNode;
}) { return <WorkspaceProvider><WorkspaceShell>{children}</WorkspaceShell></WorkspaceProvider>; }
