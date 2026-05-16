import AdminSidebar from "@/components/AdminSidebar";
import "../globals.css";

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen overflow-hidden antialiased" style={{ background: "var(--surface-soft)" }}>
      <AdminSidebar />
      <main className="flex-1 overflow-y-auto">{children}</main>
    </div>
  );
}
