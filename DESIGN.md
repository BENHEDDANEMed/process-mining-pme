---
name: Process Mining PME
description: Station meteo du processus -- un tableau de bord d'instruments mesurant en direct la sante d'un processus metier.
colors:
  ground: "#0a0f1e"
  panel: "#121a30"
  panel-raised: "#16213f"
  hairline: "#263252"
  ink: "#e6ebf5"
  ink-dim: "#8b98b8"
  ink-faint: "#5b688a"
  instrument: "#3da9fc"
  instrument-dim: "#1e5fa8"
  good: "#10b981"
  watch: "#f59e0b"
  storm: "#ef4444"
  neutral: "#64748b"
typography:
  display:
    fontFamily: "Space Grotesk, ui-sans-serif, system-ui, sans-serif"
    fontSize: "3rem"
    fontWeight: 700
    lineHeight: 1
  title:
    fontFamily: "Space Grotesk, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1rem"
    fontWeight: 600
  body:
    fontFamily: "Space Grotesk, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 500
  label:
    fontFamily: "Space Grotesk, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 500
    letterSpacing: "0.05em"
  reading:
    fontFamily: "Space Mono, ui-monospace, SFMono-Regular, monospace"
    fontSize: "1.5rem"
    fontWeight: 700
rounded:
  sm: "4px"
  md: "8px"
components:
  card:
    backgroundColor: "{colors.panel}"
    rounded: "{rounded.md}"
    padding: "20px"
  stat-card:
    backgroundColor: "{colors.panel}"
    rounded: "{rounded.md}"
    padding: "12px 16px"
  advisory-banner:
    backgroundColor: "{colors.watch}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "12px"
---

# Design System: Process Mining PME

## Overview

**Creative North Star: "Station meteo du processus"**

The dashboard reads as a live instrument panel, not a SaaS report. A deep marine-navy field (ground `#0a0f1e`, panel `#121a30`) holds semicircular needle dials, mono-digit readouts, and a tick-marked stat plate vocabulary borrowed from barometers and weather instruments. The one accent color at rest is the NeoMorIT instrument blue (`#3da9fc`); severity is expressed functionally, in a separate emerald/amber/red/slate scale, never by tinting the whole UI red or green. This rejects the generic light-Tailwind-dashboard template it replaced: no white cards, no single soft-shadow blue, no ambient card lift.

The build stays commercial-tool-plain rather than gauge-themed everywhere: only the Overview hero and its secondary dial row are gauges. Tables, charts, and lists elsewhere use flat panel surfaces with a hairline border -- the instrument metaphor is a signature moment, not a skin applied to every element.

One real seam exists and is handled honestly rather than hidden: the Process view embeds a backend-rendered Graphviz PNG (light background, fixed colors, cannot be retinted) inside an "instrument printout" frame -- a paper-toned panel with a mono caption strip -- so the light image reads as a deliberately mounted photograph/printout inside the dark instrument world, not a broken dark-mode gap.

**Key Characteristics:**
- Deep marine-navy field, not black or slate-gray
- One accent (instrument blue) at rest; a distinct 4-color severity scale for state
- Semicircular needle gauges as the signature, hero-only component
- Space Grotesk (UI) paired with Space Mono (every numeric reading, tabular-nums)
- Flat panels with hairline borders; no drop shadows anywhere in the dark world

## Colors

Palette is a single dark instrument-panel neutral ramp plus one always-on accent and a four-step functional severity scale that is never used for decoration.

### Primary
- **Instrument Blue** (`#3da9fc`): the NeoMorIT brand blue, used at rest for the nav active-tab underline/label, gauge sweep default, focus ring, text selection background (dimmed variant `#1e5fa8`), range-input accent, and the stat-card top accent line. This is the one color present on every screen regardless of data state.

### Secondary (severity scale, functional not decorative)
- **Good** (`#10b981`): health/gauge color when a score reads well; positive KPI state.
- **Watch** (`#f59e0b`): cautionary state; also the fixed tone of every advisory/recommendation bulletin regardless of the rule's actual severity (the API returns unranked rule strings, so the banner cannot honestly claim graded severity).
- **Storm** (`#ef4444`): critical/error state; used for the Async error message and the worst health band.
- **Neutral** (`#64748b`): a data series or state with no good/bad valence.

### Neutral
- **Ground** (`#0a0f1e`): page background.
- **Panel** (`#121a30`): card/container surface, the default resting surface.
- **Panel Raised** (`#16213f`): table header row, table hover row, chart tooltip background -- one step up for surfaces that sit inside a panel.
- **Hairline** (`#263252`): the only border color in the system; also chart gridlines and axis lines.
- **Ink** (`#e6ebf5`): primary text and numeric reading color.
- **Ink Dim** (`#8b98b8`): secondary text, labels, chart tick text, subtitles.
- **Ink Faint** (`#5b688a`): tertiary/placeholder text, scrollbar-thumb hover.

### Named Rules
**The Functional Severity Rule.** Good/watch/storm/neutral are reserved for actual computed state (health score band, error, KPI valence). They never appear as arbitrary UI decoration; a chart or panel with no severity to report stays instrument-blue or neutral ink.

**The One Accent At Rest Rule.** Instrument blue is the only color visible when nothing is being evaluated for good/bad -- nav, focus, selection, default chart bars. Introducing a second decorative accent color would fight the brand-blue commitment from PRODUCT.md.

## Typography

**Display/Body Font:** Space Grotesk (self-hosted via @fontsource, weights 500/600/700; fallback `ui-sans-serif, system-ui, sans-serif`)
**Mono/Reading Font:** Space Mono (self-hosted via @fontsource, weights 400/700; fallback `ui-monospace, SFMono-Regular, monospace`)

**Character:** A geometric grotesk for UI chrome (labels, nav, body copy) paired with a monospace exclusively for numbers -- every metric, gauge value, table cell of numeric data, and mono caption reads in Space Mono with `font-variant-numeric: tabular-nums` set globally on `body`, so instrument readouts never visually jitter or misalign.

### Hierarchy
- **Display** (700, `text-5xl`/48px, tight): the hero gauge's center readout (Process Health Score number), Space Mono.
- **Title** (600, `text-xl`/20px): app header title.
- **Headline** (600, `text-base`/16px): Card titles.
- **Body** (500 default weight of Space Grotesk, `text-sm`/14px): descriptive copy, subtitles, advisory bulletin text, interpretation text.
- **Label** (500, `text-xs`/12px, uppercase, tracked): StatCard labels, table column headers, gauge captions -- always uppercase with letter-spacing, always Space Grotesk (labels are never mono).
- **Reading** (700, `text-2xl`/24px or `text-xl`/20px compact, Space Mono): StatCard values, compact gauge center numbers, table numeric cells.

### Named Rules
**The Numbers-Are-Mono Rule.** Any value that is a live computed reading (KPI, gauge digit, table figure) renders in Space Mono. Any value that is a label, caption, or sentence renders in Space Grotesk. This is how the instrument-panel feel survives outside the gauges.

## Layout

Single centered column, `max-w-6xl` container with `px-6` gutters, shared by the header and all five view bodies. Views stack sections vertically with `space-y-6` (24px rhythm between cards). Inside a section, grids step down responsively: the KPI stat strip is `grid-cols-2` on mobile widening to `grid-cols-4` at `md`; the health-score hero splits `grid-cols-1` (stacked) below `md` into a fixed `220px` gauge column plus a flexible dial row at `md` and above. Nav tabs scroll horizontally on narrow viewports (`overflow-x-auto`, `whitespace-nowrap`) rather than wrapping or collapsing into a menu.

Card internal padding is a flat `p-5` (20px); the tighter StatCard plate uses `px-4 py-3`. There is no separate mobile density reduction beyond the grid column collapse -- padding and type scale stay constant across breakpoints.

## Elevation & Depth

Flat. No `box-shadow` appears anywhere in the dark instrument world (the one exception -- `shadow-lg` on the embedded Graphviz printout panel -- is a light-toned inset object, not part of the dark system's own depth language). Depth is conveyed by tonal layering only: ground → panel → panel-raised, each one step lighter, separated by a single 1px hairline border rather than a shadow. The health-score hero card additionally uses a radial `color-mix` gradient tinted toward its current severity color, fading back to flat panel tone -- an instrument backlight glow, not a lift effect.

### Named Rules
**The No-Shadow Rule.** Elevation is tonal, never a cast shadow. A new panel-type surface gets a lighter background + hairline border, not a `box-shadow`.

## Shapes

Corners are a single soft radius throughout: `rounded-lg` (8px) on every panel, card, table container, and advisory banner -- no sharp/square panels and no pill/fully-rounded shapes except the scrollbar thumb and gauge needle-tip circle, which are fully round to read as instrument hardware. Borders are uniformly 1px hairline (`#263252`), used instead of shadows to separate every surface from the ground behind it.

## Components

### Buttons
Only the nav tab acts as a button in this build; no standalone primary/secondary button component exists yet (no CTA surface in the shipped views). Nav tabs: no radius, bottom-border indicator only (`border-b-2`), transparent at rest, instrument-blue border + instrument-blue text when active, `text-ink-dim` → `text-ink` on hover.

### Cards / Containers
- **Corner Style:** 8px (`rounded-lg`).
- **Background:** panel (`#121a30`); the health-score hero variant additionally carries the radial severity-tinted glow.
- **Shadow Strategy:** none (see Elevation & Depth) -- tonal border only.
- **Border:** 1px hairline (`#263252`).
- **Internal Padding:** 20px (`p-5`).

### Gauge (signature component)
The semicircular needle-dial is the one component that carries the "station meteo" metaphor directly. A single component (`Gauge.jsx`) serves both the hero size (220x120 viewBox, 84px radius, 14px stroke, used once per screen for the Process Health Score) and a compact size (112x60, 42px radius, 8px stroke, used for the four secondary dimension dials). Arc track is always hairline gray; the swept arc and needle share one `color` prop driven by the health-status severity color. On mount and on every value change the arc's `stroke-dashoffset` and the needle's `rotate()` both animate over 900ms with `cubic-bezier(0.16, 1, 0.3, 1)` (ease-out) from the previous value -- the sweep-in is the component's only motion, and it always starts from 0 on first mount via a one-frame `requestAnimationFrame` delay. Center readout is always Space Mono, always the same color as the arc.

### Stat Card (label-plate)
A label-plate styled after an instrument readout: a 2px instrument-blue accent bar across the top edge, an uppercase dim label, a thin repeating-tick-mark strip (a CSS `repeating-linear-gradient` at 6px intervals) directly under the label, then the Space Mono value beneath. Always flat panel background, always 8px radius, always `px-4 py-3`. Used exclusively for single-number KPI reporting, never for text content.

### Tables
Flat panel-raised header row (uppercase, dim, tracked labels), hairline row dividers, subtle `panel-raised/60` hover tint, mono font on every data cell. Columns support an optional `wrap` flag (`min-w-[16rem]`, wraps) for long text (activity-transition names, variant sequences) versus the default `whitespace-nowrap` for short values -- this is a column-level flag, not a separate table variant.

### Advisory Banner
A single-tone recommendation bulletin: watch-amber tinted background (`watch/10`) and border (`watch/30`), an uppercase mono "Avis" tag, body text in plain ink. Deliberately carries no colored side-border and no per-item severity variation -- the backing rule engine returns unranked advisory strings, so the component does not fabricate a severity gradient it cannot back with real data.

### Charts (HBarChart, Histogram)
Recharts-based, dark-themed to match the panel world: hairline gridlines and axis lines, ink-dim tick labels, panel-raised tooltip background with hairline border, instrument-blue as the default bar color (overridable per-row via a `colorOf` callback for severity-colored bars, e.g. bottleneck ranking). Horizontal bar chart supports two-line wrapped y-axis labels for long transition names ("A →\nB"). One shared `HBarChart` serves health dimensions, activity frequency, and bottleneck ranking; no per-view chart variant.

### Instrument Printout Frame (Process view only)
The one place a real backend-rendered image (a light-background Graphviz PNG) has to sit inside the dark world without reworking the backend. Wrapped in a hairline-bordered panel with a printed graph-paper background (repeating-linear-gradient grid at 32px), containing a light paper-toned (`#f7f4ec`) card with a mono caption strip ("Relevé instrument — modèle découvert" / engine name) above the image. This reads as a mounted instrument printout rather than an unstyled light-mode leak.

### Async / Loading States
A shared three-state wrapper (`Async.jsx`): error renders storm-red text, loading renders a pulsing dim mono "Relevé en cours…" (reads as "still measuring"), success renders the children with data. Used identically across all five views -- no per-view skeleton or spinner design.

## Do's and Don'ts

### Do:
- **Do** render every live-computed number (KPI, gauge digit, table figure) in Space Mono with tabular figures; reserve Space Grotesk for labels and sentences.
- **Do** use the four-step severity scale (good/watch/storm/neutral) only for actual computed state, never as decoration.
- **Do** convey elevation with one tonal step (ground → panel → panel-raised) plus a 1px hairline border; never add a `box-shadow` to a dark-world panel.
- **Do** keep instrument-blue as the only accent visible when no severity judgment is being made (nav, focus ring, selection, default chart bars).
- **Do** frame any future backend-rendered light-background asset the same way the Graphviz PNG is framed: a paper-toned card with a mono caption strip inside a hairline panel, rather than leaving a raw light rectangle in the dark field.

### Don't:
- **Don't** add a second decorative accent color alongside instrument blue; the brand-blue commitment from PRODUCT.md means blue stays the resting-state signal.
- **Don't** invent per-item severity for the advisory banner (color-coded borders, ranked icons) — the recommendation API returns unranked rule strings, and the single watch-amber tone is the honest ceiling until the backend ranks them.
- **Don't** apply the gauge/needle-dial treatment outside the Overview health hero and its secondary dial row; it is a signature moment, not a skin for every metric.
- **Don't** use a cast shadow anywhere in the dark instrument world, including on hover states — tonal layering only.
