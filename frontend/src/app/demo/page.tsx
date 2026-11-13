"use client";

import { useRouter } from "next/navigation";
import GuestDashboard from "@/components/guest-dashboard";

export default function DemoPage() {
  const router = useRouter();
  return <GuestDashboard onSignIn={() => router.push("/login")} />;
}
