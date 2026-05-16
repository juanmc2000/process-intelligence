# UI Component Rules

## AppShell

Must include:
- fixed dark sidebar
- main content area
- optional top banner
- subtle shell divider

Do not recreate page-level layouts independently.
Use the shared AppShell pattern.

## Sidebar

Items:
- Home
- Workflows
- Uploads
- Sources
- Review Queue
- Exports
- Insights
- Settings

Bottom:
- Help
- User profile

Style:
- dark navy
- icon + label
- active state with translucent blue background
- muted inactive icons
- subtle right-edge depth

## Cards

Use:

```css
.card {
  background: #FFFFFF;
  border: 1px solid #E4E8F0;
  border-radius: 20px;
  box-shadow:
    0 1px 2px rgba(15, 23, 42, 0.04),
    0 16px 32px rgba(15, 23, 42, 0.045);
}

Cards should feel light, not boxed-in.

Buttons

Primary:

indigo
white text
medium radius
subtle shadow

Secondary:

white or transparent
border
dark text
Badges

Use rounded pills.

Status types:

Draft
Validated
High confidence
Medium confidence
Low confidence
Needs review
Exception candidate
Provenance chips

Use source chips wherever workflow information comes from evidence.

Examples:

SOP
Email
Slack
Teams
PDF
Screenshot
Ticket
Form

Provenance is mandatory for trust.

Confidence

Confidence should be visible but not dominant.

Use:

circular ring in header
small score in cards
color-coded subtle indicators
Icons

Use lucide-react.

Preferred icons:

Home
GitBranch
Workflow
Upload
Database
Layers
ClipboardCheck
FileOutput
BarChart3
Settings
Shield
Users
Lock
Search
Bell
HelpCircle
AI UX

Do not make AI the center of the interface.

Use contextual actions:

Explain this step
View evidence
Find similar steps
Suggest simplification
Standardize terminology
Generate export