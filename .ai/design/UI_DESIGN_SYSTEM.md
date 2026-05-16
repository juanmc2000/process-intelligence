# UI Design System

## Product feeling

The product should feel calm, modern, premium, spatial, operationally intelligent, and enterprise-grade.

The UI should feel like:
- understanding operations
- reconstructing workflows
- validating operational reality

It should NOT feel like:
- programming workflows
- legacy BPM software
- dense process mining dashboards
- chatbot-first AI

## Visual architecture

Use a dark enterprise shell with bright operational content.

Dark shell:
- left sidebar
- top workflow banner
- page chrome
- selected navigation

Light content:
- cards
- narrative panels
- review areas
- workflow detail areas
- evidence panels
- tables

## Palette

```css
--navy-950: #050B18;
--navy-900: #07111F;
--navy-850: #0B1628;
--navy-800: #0F1D33;

--surface: #FFFFFF;
--surface-soft: #F7F8FB;
--surface-muted: #F2F4F8;

--border-soft: #E4E8F0;
--border-strong: #CBD5E1;

--text-primary: #0F172A;
--text-secondary: #475569;
--text-muted: #94A3B8;

--accent: #4F46E5;
--accent-hover: #4338CA;
--accent-soft: #EEF2FF;

--success: #10B981;
--warning: #F59E0B;
--danger: #EF4444;

Depth treatment

The boundary between dark shell and white content must not feel flat.

Use subtle shadow and texture:

.shell-divider {
  box-shadow:
    12px 0 28px rgba(15, 23, 42, 0.16),
    inset -1px 0 rgba(255, 255, 255, 0.06);
}

.header-divider {
  box-shadow:
    0 14px 34px rgba(15, 23, 42, 0.18),
    inset 0 -1px rgba(255, 255, 255, 0.06);
}
Typography

Use Inter.

Scale:

Page title: 28–32px, 650 weight
Section heading: 18–22px, 650 weight
Card title: 15–16px, 600 weight
Body: 14–16px
Metadata: 12–13px
Button: 14px, 600 weight
Layout
Sidebar width: 230px
Top workflow banner max height: 140px
Content padding: 32–40px
Card radius: 18–22px
Button radius: 10–12px
Design guardrails
Do not create dense enterprise dashboards.
Do not use generic SaaS admin styling.
Do not make the product chatbot-first.
Do not overuse gradients.
Do not make the top banner too tall.
Use progressive disclosure.
Prefer calm spacing over crowded information.

---
