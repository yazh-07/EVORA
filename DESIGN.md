---
version: alpha
name: EVORA Investigation Workspace
description: Restrained, evidence-first operational interface with traceable states and no decorative technical theater.
colors:
  primary: "#17212B"
  secondary: "#52606D"
  accent: "#175CD3"
  neutral: "#F5F7FA"
  surface: "#FFFFFF"
  border: "#D5DCE5"
  success: "#17633B"
  warning: "#795400"
  error: "#A12B2B"
typography:
  h1:
    fontFamily: IBM Plex Sans
    fontSize: 1.5rem
    fontWeight: 600
    lineHeight: 1.3
  body-md:
    fontFamily: IBM Plex Sans
    fontSize: 1rem
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: IBM Plex Sans
    fontSize: 0.875rem
    fontWeight: 500
    lineHeight: 1.4
  identifier:
    fontFamily: IBM Plex Mono
    fontSize: 0.875rem
    fontWeight: 400
    lineHeight: 1.5
rounded:
  sm: 4px
  md: 6px
spacing:
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 32px
components:
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.surface}"
    rounded: "{rounded.sm}"
    padding: 12px
  button-primary-hover:
    backgroundColor: "#124AA9"
    textColor: "{colors.surface}"
  button-secondary:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.primary}"
    rounded: "{rounded.sm}"
    padding: 12px
  workspace:
    backgroundColor: "{colors.neutral}"
    textColor: "{colors.primary}"
  inspector:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.primary}"
    padding: "{spacing.md}"
  table-header:
    backgroundColor: "{colors.border}"
    textColor: "{colors.primary}"
  muted-label:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.secondary}"
  status-success:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.success}"
  status-warning:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.warning}"
  status-error:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.error}"
---

## Overview

Primary surface: **Operate**, with **Inspect** as secondary. This is an investigator's working application, not a marketing site, fictional control room or autonomous decision-maker. Layout prioritizes evidence selection, source verification and recorded human actions.

React/TypeScript implements the shared design. Use one reusable component system; do not independently invent styles for each view. This specification does not mean a frontend has been implemented or visually tested.

## Colors

Use neutral backgrounds, clear boundaries and one blue action accent. Status colors communicate real states and always accompany text; do not rely on color alone. Error color is reserved for actual errors, never decorative branding. No gradients, neon glow, glass blur, rainbow priority cards or color-coded claims of guilt.

## Typography

Use the specified sans family for controls and prose, with a system sans fallback if unavailable. Use the mono family for Evidence IDs, hashes and source locators, not the entire interface. Maintain readable text and tabular numeric alignment. Do not add huge dashboard slogans or tiny all-caps pseudo-terminal text.

## Layout

Desktop composition: compact navigation sidebar, case/selection header, primary evidence table or graph workspace, and a contextual detail inspector. A graph may replace the table on its own route; do not force every view into identical card grids. Preserve selection context while opening source details.

First screen to build and inspect: case evidence list plus one selected evidence inspector. Include actual filename, kind, hash/size, processing state and supported actions. Subsequent views reuse its controls and spacing. No hero section, decorative statistics or empty space filled with filler cards.

On narrow screens, collapse navigation and open the inspector as a separate panel/page. Tables may scroll within their own labeled region; primary controls must not disappear offscreen. Touch targets should be at least 44px, with visible keyboard focus and descriptive accessible names.

## Elevation

Use borders and surface contrast before shadows. Reserve a restrained shadow for overlays. Do not elevate every table row/card or use blur as a substitute for hierarchy.

## Shapes

Use small radii from the tokens. Buttons look actionable; records and read-only metadata do not resemble buttons. Avoid oversized pill containers and icon boxes on every heading.

## Components

- **Evidence table:** searchable/filterable records, stable IDs, sorting, pagination, selection and source inspector. Totals come from API totals, never the length of one page presented as the case total.
- **Processing command/status:** start explicitly, store returned run ID, poll the real state and stop on completed/failed. Retries use a fresh idempotency key; clicks must not duplicate a queued request.
- **Analysis command/status:** start an analysis, poll its returned run and pin the completed `analysis_run_id` across graph/findings/triage reads and pagination.
- **Priority view:** distinguish not scored, automated priority and manual effective override. Link factors to their actual observations/evidence. A priority is attention order, not truth or guilt.
- **Graph:** selection, readable labels, bounded case/run scope and source click-through. Candidate links remain labeled as candidates. Do not animate particles or fabricate associations.
- **Review/override:** explicit action, required reason, visible confirmation/failure and append-only history. Never show a successful write before the API confirms it.
- **Grounded answers:** claim-level source links, uncertainty and an honest unsupported state. Evidence/model text is untrusted content: render safely, never execute HTML/scripts from it.
- **Status:** only display values obtained from the API. Missing health information is unknown, not "SYSTEM ONLINE". No unrelated live clock, simulated activity ticker or invented accuracy metric.

## Do's and Don'ts

- Every visible element must support a documented investigator task; remove slogans, random technical labels and invented capabilities.
- Do not use gradients, blinking indicators, infinite pulsing, scanning effects, typewriter text or decorative loading animations.
- Allow restrained interaction transitions and actual loading feedback only; honor `prefers-reduced-motion`.
- No fabricated case counts, probabilities, model confidence, uptime or benchmark results. Development fixtures must be explicitly labeled synthetic; production views never substitute them for failed API calls.
- Implement loading, empty, error, unauthorized, not processed, not scored and unsupported-answer states rather than filling gaps with plausible text.
- No persistent browser storage of original evidence or bearer tokens. Client state is not the audit record.
- Keyboard navigation, focus visibility, accessible labels, contrast and responsive behavior are acceptance conditions, not optional decoration.
- Review the rendered first workflow before expanding. Check both screenshots and behavior/data provenance. Token lint is not browser/accessibility or application verification.
