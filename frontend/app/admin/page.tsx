// Admin / Security Portal — Overview
// Displays system health, security posture, and governance summary.

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface StatCard {
  label: string;
  value: string;
  sub: string;
  status?: "active" | "warning" | "neutral";
  action?: string;
}

interface Integration {
  name: string;
  icon: string;
  status: "Connected" | "Disconnected" | "Error";
  lastSync: string;
}

interface AuditLog {
  event: string;
  user: string;
  when: string;
}

// ---------------------------------------------------------------------------
// Static data (would come from API in production)
// ---------------------------------------------------------------------------

const STAT_CARDS: StatCard[] = [
  { label: "SSO Status", value: "—", sub: "Not connected", status: "neutral" },
  { label: "Users", value: "—", sub: "Not available", status: "neutral" },
  { label: "Data Ingestion", value: "—", sub: "Not connected", status: "neutral" },
  { label: "Anonymization", value: "—", sub: "Not configured", status: "neutral" },
  { label: "Retention Policy", value: "—", sub: "Not configured", status: "neutral" },
  { label: "Audit Events (24h)", value: "—", sub: "No data", status: "neutral" },
];

const INTEGRATIONS: Integration[] = [
  { name: "SharePoint", icon: "🔷", status: "Disconnected", lastSync: "—" },
  { name: "Slack", icon: "💬", status: "Disconnected", lastSync: "—" },
  { name: "Microsoft Teams", icon: "🟦", status: "Disconnected", lastSync: "—" },
  { name: "Email (Exchange)", icon: "📧", status: "Disconnected", lastSync: "—" },
  { name: "S3 Storage", icon: "🟠", status: "Disconnected", lastSync: "—" },
  { name: "Splunk SEM", icon: "🔴", status: "Disconnected", lastSync: "—" },
  { name: "Jira", icon: "🔵", status: "Disconnected", lastSync: "—" },
];

const SECURITY_POSTURE = [
  "RBAC enforced (planned)",
  "Admin action auditing (planned)",
  "MFA required for admins (planned)",
  "Data at rest encrypted (planned)",
  "Data in transit encrypted (planned)",
];

const AUDIT_LOGS: AuditLog[] = [];

// ---------------------------------------------------------------------------
// Stat card
// ---------------------------------------------------------------------------

function StatCard({ card }: { card: StatCard }) {
  const statusColor =
    card.status === "active"
      ? { dot: "bg-emerald-500", text: "text-emerald-600" }
      : card.status === "warning"
      ? { dot: "bg-amber-400", text: "text-amber-500" }
      : { dot: "bg-[var(--text-muted)]", text: "text-[var(--text-muted)]" };

  return (
    <div className="card p-4">
      <div className="text-[11px] font-medium text-[var(--text-muted)] mb-2 uppercase tracking-wide">
        {card.label}
      </div>
      <div className="flex items-center gap-2">
        {card.status === "active" && (
          <span className={`w-2 h-2 rounded-full shrink-0 ${statusColor.dot}`} />
        )}
        <span className="text-[20px] font-bold text-[var(--text-primary)]">{card.value}</span>
      </div>
      <div className="mt-1 flex items-center justify-between gap-2">
        <span className="text-[11px] text-[var(--text-muted)]">{card.sub}</span>
        {card.action && (
          <button className="text-[11px] font-medium text-accent hover:text-accent-hover transition-colors">
            {card.action}
          </button>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Integration row
// ---------------------------------------------------------------------------

function IntegrationRow({ item }: { item: Integration }) {
  const statusColor =
    item.status === "Connected"
      ? "text-emerald-600"
      : item.status === "Error"
      ? "text-red-500"
      : "text-[var(--text-muted)]";
  const dotColor =
    item.status === "Connected"
      ? "bg-emerald-500"
      : item.status === "Error"
      ? "bg-red-500"
      : "bg-[var(--text-muted)]";

  return (
    <div className="flex items-center gap-3 py-2.5 border-b border-[var(--border-soft)] last:border-0">
      <span className="text-lg w-7 text-center">{item.icon}</span>
      <span className="flex-1 text-[13px] font-medium text-[var(--text-primary)]">{item.name}</span>
      <span className={`flex items-center gap-1.5 text-[12px] ${statusColor}`}>
        <span className={`w-1.5 h-1.5 rounded-full ${dotColor}`} />
        {item.status}
      </span>
      <span className="text-[11px] text-[var(--text-muted)] w-16 text-right">{item.lastSync}</span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Audit log row
// ---------------------------------------------------------------------------

function AuditRow({ log }: { log: AuditLog }) {
  return (
    <div className="flex items-center justify-between py-2 border-b border-[var(--border-soft)] last:border-0">
      <span className="text-[13px] text-[var(--text-primary)]">{log.event}</span>
      <span className="text-[12px] text-[var(--text-muted)]">{log.user}</span>
      <span className="text-[11px] text-[var(--text-muted)] text-right w-14">{log.when}</span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Security posture icon
// ---------------------------------------------------------------------------

function CheckIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round" className="w-3.5 h-3.5 text-emerald-500 shrink-0">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function AdminOverviewPage() {
  return (
    <div className="flex flex-col h-full">
      {/* Page header */}
      <div className="px-8 py-6 bg-white border-b border-[var(--border-soft)]">
        <h1 className="text-[22px] font-bold text-[var(--text-primary)]">Overview</h1>
        <p className="text-[13px] text-[var(--text-muted)] mt-0.5">
          System health, security posture, and governance summary.
        </p>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-8 py-8 space-y-8">
        {/* Placeholder notice */}
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-[13px] text-amber-800">
          <span className="font-semibold">Admin portal not yet connected.</span>{" "}
          Values below reflect the planned governance structure. Real data will appear once admin APIs are integrated.
        </div>

        {/* Stat cards */}
        <div className="grid grid-cols-3 xl:grid-cols-6 gap-4">
          {STAT_CARDS.map((card) => (
            <StatCard key={card.label} card={card} />
          ))}
        </div>

        {/* Integrations + Security posture + Audit logs */}
        <div className="grid grid-cols-2 gap-6">
          {/* Integrations */}
          <div className="card p-5">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-[15px] font-semibold text-[var(--text-primary)]">Integrations</h2>
              <div className="flex gap-6">
                <span className="text-[11px] font-medium text-[var(--text-muted)] uppercase tracking-wide">Status</span>
                <span className="text-[11px] font-medium text-[var(--text-muted)] uppercase tracking-wide">Last sync</span>
              </div>
            </div>
            <div>
              {INTEGRATIONS.map((item) => (
                <IntegrationRow key={item.name} item={item} />
              ))}
            </div>
            <button disabled className="mt-4 text-[12px] font-medium text-[var(--text-muted)] cursor-not-allowed" title="Coming soon">
              Manage integrations (coming soon)
            </button>
          </div>

          {/* Right column */}
          <div className="space-y-4">
            {/* Connect sources */}
            <div className="card p-5">
              <h2 className="text-[15px] font-semibold text-[var(--text-primary)] mb-1">
                Connect sources
              </h2>
              <p className="text-[12px] text-[var(--text-muted)] mb-4 leading-relaxed">
                Connect your organisation&apos;s source systems to enable automatic artifact ingestion.
                Slack, Teams, SharePoint, Email, Jira, Confluence + more.
              </p>
              <button
                disabled
                title="Coming soon"
                className="inline-flex items-center justify-center px-4 py-1.5 rounded-btn text-[12px] font-semibold border border-[var(--border-soft)] text-[var(--text-muted)] cursor-not-allowed"
              >
                Coming soon
              </button>
            </div>

            {/* Security posture */}
            <div className="card p-5">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1">
                  <h2 className="text-[15px] font-semibold text-[var(--text-primary)] mb-3">
                    Security posture
                  </h2>
                  <div className="space-y-2">
                    {SECURITY_POSTURE.map((item) => (
                      <div key={item} className="flex items-center gap-2 text-[13px] text-[var(--text-secondary)]">
                        <CheckIcon />
                        {item}
                      </div>
                    ))}
                  </div>
                </div>
                {/* Shield badge */}
                <div
                  className="w-14 h-14 rounded-xl flex items-center justify-center shrink-0"
                  style={{ background: "var(--accent-soft)" }}
                >
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" className="w-7 h-7" style={{ color: "var(--accent)" }}>
                    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                  </svg>
                </div>
              </div>
            </div>

            {/* Recent audit logs */}
            <div className="card p-5">
              <h2 className="text-[15px] font-semibold text-[var(--text-primary)] mb-3">
                Recent audit logs
              </h2>
              {AUDIT_LOGS.length === 0 ? (
                <p className="text-[13px] text-[var(--text-muted)] italic py-2">
                  No audit data available — audit pipeline not yet connected.
                </p>
              ) : (
                <div>
                  {AUDIT_LOGS.map((log) => (
                    <AuditRow key={log.event + log.when} log={log} />
                  ))}
                </div>
              )}
              <button disabled className="mt-4 text-[12px] font-medium text-[var(--text-muted)] cursor-not-allowed" title="Coming soon">
                View all audit logs (coming soon)
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
