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
  { label: "SSO Status", value: "Active", sub: "Okta", status: "active" },
  { label: "Users", value: "128", sub: "Active users", status: "neutral" },
  { label: "Data Ingestion", value: "7", sub: "Sources connected", status: "neutral" },
  { label: "Anonymization", value: "Active", sub: "PII masking enabled", status: "active" },
  { label: "Retention Policy", value: "90 days", sub: "Time to auto-delete", status: "neutral" },
  { label: "Audit Events (24h)", value: "342", sub: "", action: "View logs", status: "neutral" },
];

const INTEGRATIONS: Integration[] = [
  { name: "SharePoint", icon: "🔷", status: "Connected", lastSync: "5m ago" },
  { name: "Slack", icon: "💬", status: "Connected", lastSync: "1m ago" },
  { name: "Microsoft Teams", icon: "🟦", status: "Connected", lastSync: "1m ago" },
  { name: "Email (Exchange)", icon: "📧", status: "Connected", lastSync: "3m ago" },
  { name: "S3 Storage", icon: "🟠", status: "Connected", lastSync: "10m ago" },
  { name: "Splunk SEM", icon: "🔴", status: "Connected", lastSync: "1m ago" },
  { name: "Jira", icon: "🔵", status: "Connected", lastSync: "6m ago" },
];

const SECURITY_POSTURE = [
  "RBAC enforced",
  "All admin actions audited",
  "MFA required for admins",
  "Data at rest encrypted",
  "Data in transit encrypted",
];

const AUDIT_LOGS: AuditLog[] = [
  { event: "Admin login", user: "michael.chen", when: "2m ago" },
  { event: "Role updated", user: "michael.chen", when: "10m ago" },
  { event: "Retention policy changed", user: "system", when: "1h ago" },
  { event: "Source connected", user: "sarah.johnson", when: "2h ago" },
  { event: "Anonymization rules updated", user: "michael.chen", when: "3h ago" },
];

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
  return (
    <div className="flex items-center gap-3 py-2.5 border-b border-[var(--border-soft)] last:border-0">
      <span className="text-lg w-7 text-center">{item.icon}</span>
      <span className="flex-1 text-[13px] font-medium text-[var(--text-primary)]">{item.name}</span>
      <span className="flex items-center gap-1.5 text-[12px] text-emerald-600">
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
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
            <button className="mt-4 text-[12px] font-medium text-accent hover:text-accent-hover transition-colors">
              Manage integrations →
            </button>
          </div>

          {/* Right column */}
          <div className="space-y-4">
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
              <div>
                {AUDIT_LOGS.map((log) => (
                  <AuditRow key={log.event + log.when} log={log} />
                ))}
              </div>
              <button className="mt-4 text-[12px] font-medium text-accent hover:text-accent-hover transition-colors">
                View all audit logs →
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
