
---

## 2. `.ai/design/UI_PAGE_BRIEFS.md`

```md
# UI Page Briefs

## Main sections

The product has four main sections:

1. Home / Workspace
2. Spatial Workflow
3. Workflow Narrative
4. Admin / Security Portal

---

# 1. Home / Workspace

Purpose:
- upload files
- see recent runs
- see workflow reconstruction status
- guide users into review and exploration

Layout:
- dark left sidebar
- light workspace content
- upload card
- recent workflow cards
- review queue summary
- system status / confidence summary

Primary actions:
- Upload files
- View recent workflow
- Continue review
- Open process explorer

Tone:
- simple
- approachable
- operational
- low friction

---

# 2. Spatial Workflow

Purpose:
- visually inspect reconstructed workflow structure

Should include:
- workflow graph canvas
- workflow steps
- systems
- roles
- approvals
- handoffs
- controls
- exceptions
- confidence indicators
- evidence/source chips

UX:
- spatial and calm
- zoom/pan
- click node for detail
- avoid technical BPM clutter
- workflow should feel understandable to operators

---

# 3. Workflow Narrative

Purpose:
- explain the workflow in plain English before showing the diagram

Structure:
- dark sidebar
- dark top workflow banner
- white tab row
- narrative-first content

Top banner:
- breadcrumb
- workflow title
- draft badge
- confidence ring
- owner/status metadata
- Explore workflow button
- Share / Export buttons

Tabs:
- Narrative
- Workflow
- Sources
- Insights
- Activity

Content:
- left column: workflow summary and key findings
- right column: at-a-glance, confidence, ambiguities, next steps

Tone:
- operational briefing
- plain English
- no process-mining jargon

---

# 4. Admin / Security Portal

Purpose:
- governance and enterprise controls

Sections:
- integrations
- SSO
- RBAC
- audit logging
- retention policies
- SIEM integrations
- connector management
- anonymization controls

Tone:
- serious
- secure
- sparse
- trustworthy

Do not overdesign admin.
Operator portal is the main product experience.