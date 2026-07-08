import { requireSession } from "@/lib/authz";
import { AppShell } from "@/components/app-shell";
import { ChangePasswordForm } from "./change-password-form";

export default async function ProfilePage() {
  const session = await requireSession();
  return (
    <AppShell session={session}>
      <h1 className="mb-4 text-2xl font-semibold">My Profile</h1>
      <div className="max-w-md">
        <ChangePasswordForm />
      </div>
    </AppShell>
  );
}
