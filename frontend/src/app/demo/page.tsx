"use client";

import { useRouter } from "next/navigation";
import GuestDashboard from "@/features/workspace/demo-view";

export default function DemoPage() {
  const router = useRouter();
  return <GuestDashboard onSignIn={() => router.push("/login")} />;
}
