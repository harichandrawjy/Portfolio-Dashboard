---
name: Raster
description: A Swiss modular grid for a financial instrument — one grotesk, black rules, and a single deep-sea blue used at poster scale.
colors:
  bg: "#ffffff"
  panel: "#ffffff"
  panel-2: "#eef0f4"
  panel-3: "#e0e3e9"
  line: "rgb(10 12 16 / 0.15)"
  line-2: "rgb(10 12 16 / 0.9)"
  ink: "#0a0c10"
  ink-2: "#3a4150"
  ink-3: "#5c6373"
  accent: "#084d77"
  accent-hover: "#063a5b"
  accent-ink: "#084d77"
  accent-glow: "rgb(8 77 119 / 0.45)"
  on-accent: "#ffffff"
  on-accent-muted: "rgb(255 255 255 / 0.7)"
  pos: "#126b46"
  pos-hover: "#0d5537"
  neg: "#bc1f33"
  neg-hover: "#9d1929"
  warn: "#7d5710"
  chart-sea: "#084d77"
  chart-violet: "#8a4fb8"
  chart-gold: "#b07a20"
  chart-terracotta: "#a34a28"
  chart-sky: "#7bb2d9"
  chart-rose: "#99486e"
  chart-olive: "#4f7a2f"
  chart-neutral: "#767d8c"
typography:
  display:
    fontFamily: "Archivo Variable, ui-sans-serif, system-ui, sans-serif"
    fontSize: "clamp(2.75rem, 7vw, 5.5rem)"
    fontWeight: 800
    lineHeight: 0.88
    letterSpacing: "-0.03em"
    fontVariation: "wdth 86"
    textTransform: "uppercase"
  figure:
    fontFamily: "Archivo Variable, ui-sans-serif, system-ui, sans-serif"
    fontSize: "clamp(3rem, 8.5vw, 5.75rem)"
    fontWeight: 800
    lineHeight: 0.86
    letterSpacing: "-0.035em"
    fontVariation: "wdth 86"
    fontFeature: "tnum"
  hero-figure:
    fontFamily: "Archivo Variable, ui-sans-serif, system-ui, sans-serif"
    fontSize: "clamp(2.5rem, 5.5vw, 3.5rem)"
    fontWeight: 800
    lineHeight: 0.88
    letterSpacing: "-0.03em"
    fontVariation: "wdth 86"
    fontFeature: "tnum"
  nameplate:
    fontFamily: "Archivo Variable, ui-sans-serif, system-ui, sans-serif"
    fontSize: "clamp(2rem, 4.5vw, 2.75rem)"
    fontWeight: 800
    lineHeight: 0.92
    letterSpacing: "-0.02em"
    fontVariation: "wdth 86"
    textTransform: "uppercase"
  form-heading:
    fontFamily: "Archivo Variable, ui-sans-serif, system-ui, sans-serif"
    fontSize: "34px"
    fontWeight: 800
    lineHeight: 0.92
    letterSpacing: "-0.02em"
    fontVariation: "wdth 86"
    textTransform: "uppercase"
  card-figure:
    fontFamily: "Archivo Variable, ui-sans-serif, system-ui, sans-serif"
    fontSize: "30px"
    fontWeight: 800
    lineHeight: 1
    letterSpacing: "-0.02em"
    fontVariation: "wdth 86"
    fontFeature: "tnum"
  stat:
    fontFamily: "Archivo Variable, ui-sans-serif, system-ui, sans-serif"
    fontSize: "22px"
    fontWeight: 700
    lineHeight: 1
    fontFeature: "tnum"
  stat-sm:
    fontFamily: "Archivo Variable, ui-sans-serif, system-ui, sans-serif"
    fontSize: "19px"
    fontWeight: 700
    lineHeight: 1
    fontFeature: "tnum"
  wordmark:
    fontFamily: "Archivo Variable, ui-sans-serif, system-ui, sans-serif"
    fontSize: "19px"
    fontWeight: 800
    lineHeight: 1
    letterSpacing: "0.16em"
    fontVariation: "wdth 112"
    textTransform: "uppercase"
  brand-stat:
    fontFamily: "Archivo Variable, ui-sans-serif, system-ui, sans-serif"
    fontSize: "17px"
    fontWeight: 700
    lineHeight: 1
    fontFeature: "tnum"
  lede:
    fontFamily: "Archivo Variable, ui-sans-serif, system-ui, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.6
  body:
    fontFamily: "Archivo Variable, ui-sans-serif, system-ui, sans-serif"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.6
  data:
    fontFamily: "Archivo Variable, ui-sans-serif, system-ui, sans-serif"
    fontSize: "13px"
    fontWeight: 500
    lineHeight: 1.2
    fontFeature: "tnum"
  caption:
    fontFamily: "Archivo Variable, ui-sans-serif, system-ui, sans-serif"
    fontSize: "12px"
    fontWeight: 700
    lineHeight: 1
    letterSpacing: "0.14em"
    fontVariation: "wdth 112"
    textTransform: "uppercase"
  control:
    fontFamily: "Archivo Variable, ui-sans-serif, system-ui, sans-serif"
    fontSize: "11px"
    fontWeight: 700
    lineHeight: 1
    letterSpacing: "0.12em"
    textTransform: "uppercase"
  meta:
    fontFamily: "Archivo Variable, ui-sans-serif, system-ui, sans-serif"
    fontSize: "11px"
    fontWeight: 400
    lineHeight: 1.4
    fontFeature: "tnum"
  micro:
    fontFamily: "Archivo Variable, ui-sans-serif, system-ui, sans-serif"
    fontSize: "10px"
    fontWeight: 700
    lineHeight: 1
    letterSpacing: "0.14em"
    fontVariation: "wdth 112"
    textTransform: "uppercase"
rounded:
  sm: "0px"
  md: "0px"
  lg: "0px"
  xl: "0px"
  full: "9999px"
spacing:
  page-x: "16px"
  page-y: "24px"
  panel-x: "20px"
  panel-y: "12px"
  stack: "40px"
  field: "16px"
  hairline: "1px"
  container: "1200px"
components:
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.on-accent}"
    rounded: "{rounded.md}"
    padding: "10px 16px"
  button-primary-hover:
    backgroundColor: "{colors.accent-hover}"
  button-ghost:
    textColor: "{colors.ink}"
    borderColor: "{colors.line-2}"
    rounded: "{rounded.md}"
    padding: "10px 16px"
  button-ghost-hover:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.bg}"
  button-danger-solid:
    backgroundColor: "{colors.neg}"
    textColor: "#ffffff"
    rounded: "{rounded.md}"
    padding: "10px 16px"
  input-field:
    backgroundColor: "{colors.panel-2}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "10px 12px"
  input-field-focus:
    backgroundColor: "{colors.panel}"
    borderColor: "{colors.accent}"
  panel-raised:
    backgroundColor: "{colors.panel}"
    borderTop: "3px solid {colors.line-2}"
    rounded: "{rounded.md}"
  panel-flat:
    borderTop: "1px solid {colors.line}"
    rounded: "{rounded.md}"
  hero-field:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.on-accent}"
    rounded: "{rounded.md}"
    padding: "24px"
  segmented-item-active:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.bg}"
    rounded: "{rounded.md}"
    padding: "6px 12px"
  modal-sheet:
    backgroundColor: "{colors.panel}"
    borderColor: "{colors.ink}"
    rounded: "{rounded.md}"
    width: "28rem"
  modal-header:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.bg}"
---

# Design System: Raster

## Overview

**Creative North Star: "Rastersysteme"**

Raster takes the Swiss International Typographic Style at its word and
applies it to a financial instrument. There is one grotesk, drawn at extreme
size contrast on both a weight and a *width* axis. There are no cards, no
shadows, no gradients, no texture, and no rounded corners. Structure is
carried entirely by black rules and a numbered modular grid: every major
section announces itself with a two-digit sequence number, a wide
letterspaced caption, and a rule drawn across the full measure.

The single deep-sea blue is never a tint and never a link colour. It is
either absent, or it is the whole surface — a flat poster-scale field with
knockout type. The page's hierarchy comes from the size jump between a 10px
caption and a 92px figure, not from boxes, elevation, or colour variety.

Underneath the poster the register is analytical and dense. Every figure is
tabular so columns align down the page, tables sort in place, hairlines do
the dividing, and controls answer in 160ms without ceremony.

**Key characteristics:**

- One typeface, two axes — weight 100–900 and width 62–125%
- Numbered sections (`01`, `02`, `03`) as the primary structural device
- Black rules instead of cards; nothing is raised or shadowed
- The page ends on a full-bleed accent field, not on trailing whitespace
- One accent — a deep-sea blue — deployed only as a full flat field
- Square everything — the radius scale is zeroed
- Tabular figures everywhere a number appears
- Print-grade green and red reserved strictly for signed values

## Colors

### Primary

- **Deep Sea** (`{colors.accent}`): the one colour. Used at full strength as a
  filled field — the total-value block, the login brand half, the primary
  button — and as the colour of every sequence number. Never a tint, never a
  background wash behind body text, never a link colour.

  It replaced a muted ink-indigo (`#2b3570`) that read as corporate navy, the
  exact register this project has rejected twice. **The cyan chroma is what
  keeps it oceanic rather than corporate** — desaturating it drops it straight
  back into navy, so if this is ever retuned, hold the chroma and move the
  lightness. It also earns the product's name: *arus* is Indonesian for
  current.

  Verified by perceptual distance rather than hue angle: ΔE2000 **34** from
  the gain green and **45** from the loss red, so a filled block of it can
  never be misread as data. **8.98:1** on white — and because contrast is
  symmetric, that one figure governs both knockout type on the field and
  accent type on paper.
- **Knockout** (`{colors.on-accent}`): pure white type on the accent field.
- **Accent glow** (`{colors.accent-glow}`): the accent at 45%, used only for
  the lot slider's focus ring — the single place the accent appears at
  partial alpha, and a focus affordance rather than a surface.

### Secondary

- **Print Green** (`{colors.pos}`) and **Print Red** (`{colors.neg}`): signal
  only, for the sign of a financial value.
- **Print Amber** (`{colors.warn}`): caution and concentration flags.

### Tertiary — the chart palette

A designed set of **seven** series, not a cycling ramp. Slot 1 is always the
accent, so a portfolio's own line is the same colour as the interface around
it. Slots are assigned in fixed canonical sector order and never recycled;
anything past the seventh folds into "Other" in **Chart Neutral**
(`{colors.chart-neutral}`), which also draws the IHSG benchmark so it never
competes with a holding.

**Why seven and not eight.** Three hues are unavailable — green, red and
amber mean the sign of a value and nothing else — and the deep-sea accent now
occupies the blue region too. Every candidate eighth slot was measured with
CIEDE2000 against the other seven, the benchmark grey, and both signal
colours; all landed under ΔE 15 on some pair (deep teal 15 vs the gain green,
umber 13 vs terracotta, steel 11 and slate 14 vs the accent itself, pink 10
vs rose). Seven is the honest ceiling. Note that **Sky**
(`{colors.chart-sky}`) is separated from the accent by *lightness*, not hue —
with blue spoken for, that is the only axis left.

Known residual tension, inherited from the previous palette: terracotta sits
ΔE 13 from the loss red and olive ΔE 13 from the gain green. Both are late
slots that appear only in wide portfolios, and the signal colours appear as
*text* while these appear as labelled *fills*, so the two never compete in
the same role. Retune them before adding any new series.

### Neutral

- **Paper** (`{colors.bg}` / `{colors.panel}`): pure white. The ground and the
  regions on it are the same sheet — regions are bounded by rules, not by a
  change of tone.
- **Fill** (`{colors.panel-2}`): the only fill tone — inputs, tracks, wells,
  meters, row hover. **Deep Fill** (`{colors.panel-3}`) for a well inside a fill.
- **Ink** (`{colors.ink}`): a true near-black. The contrast between ink and
  paper is what carries the poster.
- **Secondary / Muted Ink** (`{colors.ink-2}`, `{colors.ink-3}`): supporting
  text and metadata. `ink-3` is the quiet floor — it clears 4.5:1 on white
  and nothing quieter may be introduced beneath it.
- **Hairline** (`{colors.line}`) and **Rule** (`{colors.line-2}`): the
  dividing system. `line` separates rows inside a block; `line-2` is the
  near-black structural rule that opens a section and draws a control's edge.

### Named Rules

**The Full Field Rule.** The accent is either a full-strength filled surface
or it is absent. It never appears as a 10% tint, a pastel band, or a link
colour. Its rarity and its saturation are the same decision.

**The Print-Grade Sign Rule.** Green and red carry exactly one meaning: the
sign of a financial value. They never indicate status, category, or brand.

**The Order-Entry Exception.** There is exactly one sanctioned exception, and
it is deliberate rather than drift: the **buy/sell side control inside the
order modals** — the `BinaryToggle` and the commit button that restates it.
Green buy / red sell is the convention every IDX broker uses, and the mistake
it guards against (recording a sell as a buy) is expensive and easy, because
before this the two modes were distinguishable only by reading the label.

The exception is tightly scoped, and the scope is the reason it is safe:

- **Only inside the order modals**, where no signed figure shares the surface
  to compete with it. Verify this stays true if a P&L is ever added there.
- **Not in the holdings table.** Those row buttons sit two cells from the P&L
  column and stay neutral (ink outline, inverting on hover). This means the
  same action is coloured in one place and not the other — a real
  inconsistency, accepted knowingly in exchange for keeping the P&L column
  unambiguous.
- **Not the cash modal.** Deposit/Withdraw keeps the accent: money moving in
  is not a gain, and money moving out is not a loss.
- **Not `dangerSolid`.** Sell uses its own `sell` variant. A sell is not a
  destructive action, and conflating them would make red mean two things.

Anything outside that scope is still governed by the rule above.

**The No Fainter Rule.** `{colors.ink-3}` is the quiet floor. Never dim a
text token with an opacity modifier to make it quieter; reach for the next
token down, and if there isn't one, the text is already as quiet as it goes.
Opacity on ink is for rules and fills, not for type.

**The Rules Carry It Rule.** A region is defined by the rule above it, never
by a background tone, a border box, or a shadow. If removing the rule makes
the region vanish, the region is wrong — strengthen the rule.

## Typography

**One family:** Archivo Variable (with `ui-sans-serif`, `system-ui` fallback),
self-hosted via `@fontsource-variable/archivo/wdth.css`. No network font
requests, no layout shift, no second typeface.

The `serif` and `mono` font tokens deliberately resolve to Archivo as well,
so any stray `font-serif` / `font-mono` utility renders correctly instead of
falling back to Times or Courier.

**Character:** A grotesque with a genuine width axis. Display type is drawn
**condensed and heaviest** (`wdth 86`, weight 800) so a large figure reads as
a printed mark rather than as big body text. Captions and labels are drawn
**wide** (`wdth 112`) and letterspaced, the way a caption sits under a plate
in a Swiss book. The two extremes are the same typeface, which is what makes
the system read as one system.

Two utilities express this: `.w-condensed` and `.w-wide`.

### Hierarchy

The ramp is deliberately gapped — there is nothing between 34px and 22px,
because the system creates hierarchy by *jumping*, not by stepping.

- **Display** (800, clamp 44–88px, condensed, uppercase): the login statement.
- **Figure** (800, clamp 48–92px, condensed, tabular): the page's poster
  number — aggregate net worth. One per surface, at most.
- **Hero figure** (800, clamp 40–56px, condensed, tabular): the number inside
  an accent field.
- **Nameplate** (800, clamp 32–44px, condensed, uppercase): a page's title.
- **Card figure** (800, 30px, condensed, tabular): the headline number on a
  card in a grid.
- **Stat / Stat-sm** (700, 22px / 19px, tabular): figures in a definition grid.
- **Wordmark** (800, 19px, wide, 0.16em, uppercase): "ARUS" plus its accent
  square. Never used for anything that is not the name.
- **Body / Data** (400–500, 13px): interface copy and table cells.
- **Caption** (700, 12px, wide, 0.14em, uppercase): section and panel titles.
- **Control** (700, 11px, 0.12em, uppercase): button and field labels.
- **Micro** (700, 10px, wide, 0.14em, uppercase): column heads, eyebrow
  labels. The floor of the scale — never body copy.

### Named Rules

**The Tabular Figure Rule.** Every number carries `tabular-nums` via the
`.tnum` class. Digits must occupy identical widths so a column of rupiah
aligns down the page and a changing quote does not shift its neighbours.
This is mechanical, not stylistic, and it is not negotiable. Archivo's
`tnum` feature was verified in-browser before the family was adopted — any
replacement family must be verified the same way.

**The One Family Rule.** There is no second typeface and no third voice. A
new surface that wants contrast reaches for the width axis, the weight axis,
or the size ramp — never for another font.

**The Uppercase Register.** All labels, captions, controls and column heads
are uppercase and letterspaced. Sentence case is reserved for body copy,
hints, and data.

## Layout

Every page is a single centered measure: `1200px` maximum with `16px`
gutters, no sidebars, no nested containers. Sections stack in a `40px`
rhythm — much looser than the previous system, because the rules need air
to read as structure rather than as clutter.

The dominant pattern is an asymmetric split rather than a grid of equal
boxes: the portfolio summary is `minmax(300px, 0.9fr) 1.5fr`, so the accent
field stays substantial while the supporting figures spread across the wider
half as a hairline-bedded row. The login is `1.15fr 1fr`, brand half
dominant, collapsing to the form alone below `lg`.

**The hairline bed.** Definition rows are laid out as `gap-px bg-line` with
each cell painting its own `bg-bg`. The gaps themselves become the rules, so
cells can appear and disappear without any per-cell border logic to keep in
sync. This is the system's standard way to rule a group of figures.

**The bed must flex, not sit in fixed tracks.** This is load-bearing, not a
preference. Several of these cells are conditional — Realized P&L only exists
once something has been sold, Cash only once the portfolio is funded — so a
fixed `grid-cols-3` leaves one or two tracks with no cell to paint them, and
the bed shows through as a **grey block**. Use `flex flex-wrap` with
`flex-1 basis-[Npx]` cells so the last row always grows to fill the measure
and the bed is only ever visible as the 1px gaps it is meant to be. A fixed
grid is safe here *only* when the number of children is a constant.

Responsive behaviour is deliberately simple: a single column on small
screens, splits engage at `lg`, display type steps up by clamp. Tables scroll
horizontally inside their region rather than reflowing into stacked cards,
with the ticker column pinned. Density stays constant across breakpoints —
this is an instrument, and a phone gets the same figures.

### Named Rules

**The One Measure Rule.** Every page lives in the same `1200px` column with
the same `16px` gutter. New surfaces do not introduce their own width.

### The ground stays plain

The page ground is white and carries nothing — no texture, no tint, no
pattern. A faint column raster was built here and **removed**: at the alpha
that kept it behind the type it composited to `#eef3f5`, **1.119:1** against
white, which is below what a 1px rule needs to register on a normal display.
Anything strong enough to read would have competed with the tables. Record
this so it is not attempted a third time.

Presence comes instead from the **colophon** (see Components) — a flat accent
surface, which is a *surface* rather than a texture, so the flat rule holds.

**The short-page rule.** The shell is `flex min-h-[100dvh] flex-col` with
`main` on `flex-1`, so on a short page the colophon is pushed to the bottom
of the viewport and no blank strip is ever left beneath it. On a long page it
simply follows the content. Any new full-height layout must preserve this.

**The Numbered Section Rule.** A major section opens with `SectionHead` — a
two-digit sequence number in accent, a wide uppercase title, and a rule drawn
across the measure. Panels inside a page use `PanelHeader` with the same
sequence device. Numbers are decorative and are marked `aria-hidden`.

## Elevation & Depth

**There is none.** This system is flat by commitment. No `box-shadow`, no
`backdrop-filter`, no glass, no blur, no grain, no light source. The previous
system's paper grain and corner wash were removed outright.

The colophon field is a **surface, not a layer**: a flat area of accent that
the page ends on. It sits in normal flow, casts nothing, and is never
overlapped. Nothing in this system is ever above anything else.

Separation is achieved by, in order: a rule, a change of fill, an inversion
to solid ink. The only true z-plane is the modal, which earns it with a
`bg-ink/50` overlay and a 1px ink ring — not a shadow.

### Named Rules

**The Flat Rule.** If a surface needs to separate from its neighbour, rule it
or invert it. Never reach for a shadow; the system has no shadow vocabulary
to reach for.

## Shapes

**Everything is square.** The radius scale (`--radius-xs` through
`--radius-3xl`) is zeroed in `@theme`, so `rounded`, `rounded-md`,
`rounded-xl` and friends are all flat — a stray utility cannot reintroduce a
corner.

`rounded-full` is a separate register with one narrow job: genuinely circular
marks. It is never a container, never a chip, never a badge. Status labels
are square. Meters and tracks are square. The lot slider's thumb is a
square 4×20px bar.

Borders are rules, not strokes: `border-t-[3px] border-line-2` opens a major
region, `border-b-2 border-ink` sits under table heads, `border-l-[3px]`
marks an error note, and `border-line` hairlines separate rows.

### Named Rules

**The Zero Radius Rule.** Nothing in this system is rounded except a
genuinely circular mark. There is no second radius register to choose from.

**The Square Chip Rule.** A status label, count, or badge is a square block
or plain text. Pills belong to the previous system.

## Components

### Buttons

- **Shape:** square, flat, no border on filled variants.
- **Label:** 11px, weight 700, uppercase, `0.12em` tracking. A pressed label,
  not a soft chip.
- **Primary:** a flat field of accent with knockout white.
- **Ghost:** transparent with a near-black `line-2` hairline, **inverting to
  solid ink with paper text on hover**. This inversion is the system's
  standard interactive answer.
- **Danger / Danger Solid:** the same two shapes in red; solid red is reserved
  for the confirmed destructive step inside a dialog.
- **Focus:** a 2px accent ring with a 2px page-ground offset — never a browser
  default outline.
- **Busy state:** the label is replaced with "Working…" and the button
  disables. There are no spinners in this system.
- **Press feedback** is the `.press` class, in two separable layers. **Colour**
  is the base and always applies — it is the hard state flip, it survives
  `prefers-reduced-motion`, and on touch, where no hover ever fires, it is the
  only thing that can acknowledge a tap. **Scale** (`0.97`, 120ms) is the
  enhancement and is gated on motion preference. `0.97` is a depression, not a
  bounce: no overshoot, no elastic curve, nothing that contradicts
  "mechanical, precise."
- **Actions press; selections do not.** Anything that performs an action
  carries `.press` — every `Button` variant, the ledger's edit/delete icons,
  the holdings row's Buy/Sell. Selection controls — `Segmented`,
  `BinaryToggle`, the sortable column heads — are excluded on purpose: their
  state changing *is* the feedback, and they are toggled often enough that a
  squish per tap becomes noise.

### Regions (`Panel`)

Two tones, one component, no box.

- **Raised** (default): white, opened by a `3px` near-black rule across the top.
- **Flat:** transparent, opened by a `1px` hairline.
- **Header** (`PanelHeader`): sequence number in accent, then the title as a
  12px wide uppercase caption, then an optional tabular count, then an
  optional action on the right, baseline-aligned.

### Inputs / Fields

A filled grey square with **no resting border** — borders on every field
would out-shout the structural rules that carry the page. The field states
itself by fill and only draws an edge when focused: background lifts to
paper, ring becomes 2px accent. The label above is 11px uppercase wide.

### Segmented control

A `panel-2` track with square items. The selected segment **inverts to solid
ink**. No sliding pill, no shadow, no radius.

**An unselected segment reads as a caption unless something answers the
pointer.** On a white page an unfilled segment is the same colour as the
ground, so the filled one looks like a label with text beside it rather than
one of two slots. The fix is NOT to fill the unselected side or box the
group — both were tried and both fight the plain ground. Instead:

- the label is `ink-2`, not `ink-3`. The quiet floor makes an available
  option look disabled;
- hover fills `panel-2`, the same answer the data table gives a row;
- `cursor: pointer` is restored (see the Do below), so the pointer confirms
  the whole strip before anything is clicked.

At rest the control stays flat on the ground, which is the point. The
frontier's two switchers are the hairline-bed variant — `gap-px bg-line`,
so the bed shows only as a rule *between* items. Selected inverts to ink, or
to accent where the group is a binary choice (see `BinaryToggle`).

### Data table

The densest surface. Column heads are 10px uppercase wide micro labels, each
a sort toggle, sitting on a `2px` near-black rule; the active column's label
turns accent. Rows are separated by hairlines, last row unruled, with a
`panel-2` fill on hover. The ticker cell stacks a bold wide uppercase symbol
over a truncated company name; the symbol turns accent on row hover. Every
numeric cell is tabular and right-aligned; missing prices sort to the bottom
rather than reading as zero. Weight is a square meter on a flat track.

### Hero field

The signature component. The page's headline number knocked out of a flat
accent field: a 10px uppercase label at 75% white, then the figure in
condensed 800 at 40–56px, then a quiet as-of line. It enters with
`.field-wipe`, uncovering left-to-right like ink laid by a press. It is the
one place per page where the accent takes over completely.

### Colophon

The page ends in a **full-bleed field of the accent** carrying an oversized
knockout wordmark, cropped by the field's own bottom edge. It exists because
a short page left a large blank region under the content with nothing to do;
a flat colour field ends the page deliberately instead of letting it trail
off into whitespace.

It is a surface, not an ornament — it holds the data provenance (`963 IDX
tickers`, `5y daily bars`, `IHSG benchmark`) and the not-real-money
disclaimer, which have to live somewhere regardless. Every entry in that row
is a measured figure; a fourth slot was removed rather than filled with a
word set in a figure's clothing.

- **Full bleed is the one sanctioned exception to the One Measure Rule.** The
  *field* spans the viewport; everything *inside* it stays in the same
  `1200px` measure as every other page. Do not let content escape the measure.
- **The mark bleeds.** `overflow-hidden` on the field plus a negative bottom
  margin crops the wordmark at the baseline, which is what makes it read as a
  printed mark rather than as very large text. It is `aria-hidden` and
  `select-none` — decorative, and the masthead already names the product.
- **Muted knockout is `{colors.on-accent-muted}`** — white at 70%, which
  composites to `rgb(181, 202, 214)` on the accent for **5.3:1**. That is the
  quiet floor on an accent field; nothing may go below it. Measure knockout
  text by compositing through a canvas, not by parsing the computed colour —
  modern browsers return `oklab(… / α)` and naive parsing reports nonsense.

### Motion

Motion is mechanical: quick, precise, no bounce, no overshoot. **This is a
working instrument opened many times a day, so routine motion is feedback —
never choreography the user waits through.** Frequency decides whether an
animation belongs at all: something seen a hundred times a day gets none,
something seen once per session may be authored.

**The scale** (tokens in `styles.css`; reach for a token, not a new number):

| Token | Value | Use |
|---|---|---|
| `--motion-feedback` | 120ms | press, toggle |
| `--motion-state` | 180ms | hover, colour, focus |
| `--motion-enter` | 260ms | section entry |
| `--motion-exit` | 150ms | anything leaving |
| `--motion-overlay` | 220ms | modal, toast |
| `--motion-focal` | 750ms | the login field — once per session only |

`--ease-out` (`cubic-bezier(0.23, 1, 0.32, 1)`) for arriving and leaving;
`--ease-move` (`cubic-bezier(0.77, 0, 0.175, 1)`) for travel between two known
positions.

### Named Rules

**No ease-in, ever.** It delays the exact moment the user is watching.
Entering and exiting are `ease-out`; moving and morphing are `ease-in-out`.

**Exit is always faster than entrance.** A dismissal should feel answered,
not replayed. The modal and toast hold themselves mounted for `--motion-exit`
so they can leave; if you change one of those durations, change the other.

**Cap every stagger.** The section stagger is `40ms` clamped at index 3, so a
page settles at `120 + 260 = 380ms` no matter how many items it has. An
uncapped stagger makes the page slower the more data you own, which penalises
exactly the users with the most to read.

**Opacity and transform only.** `.rise` deliberately does not animate
`clip-path`: the blocks it runs on reach ~1100px tall, and repainting that
area on every navigation is not worth a hard-edged wipe.

**Charts do not animate.** Both `PerformanceChart` lines and the
`AllocationDonut` set `isAnimationActive={false}`. Recharts defaults to a
1500ms `ease` draw that replays on every mount *and* every range change —
five times the ceiling for routine UI, on the figures people came to read.

**Numbers never animate.** No count-ups, no rolling digits. The whole
tabular-figure rule exists so digits hold still; a counter would fight it and
delay the value.

**Data swaps are instant, not crossfaded.** Changing the chart range replaces
the line in one frame on purpose. A crossfade was considered and rejected: it
reintroduces ~150ms of double-exposure where neither period is readable, which
is precisely the cost that removing the 1500ms draw was meant to eliminate.
Switching range is a *comparison*, so the new data must be legible
immediately.

**Gate hover motion**, not just colour: `@media (hover: hover) and
(pointer: fine)`, or a tap leaves the hover state stuck on. Focus states are
never gated — the keyboard path must always work.

Everything is suppressed under `prefers-reduced-motion: reduce`, including the
dialog's exit *delay* — there is no reason to postpone an unmount for an
animation that will not run.

The modal enters on a short translate with **no scale**; a dialog is a sheet
placed down, not something that zooms. The skeleton pulses rather than
shimmering — a moving highlight implies a light source this system does not
have.

## Do's and Don'ts

### Do

- **Do** use the accent as a full flat field or not at all (The Full Field Rule).
- **Do** open every major section with a numbered `SectionHead`.
- **Do** set every number with `.tnum`, no exceptions.
- **Do** rule regions instead of boxing them; use the hairline bed
  (`gap-px bg-line`) for definition grids.
- **Do** reach for the width axis (`.w-condensed`, `.w-wide`) for contrast.
- **Do** keep all pages inside the single `1200px` measure.
- **Do** reserve green and red for the sign of a financial value.
- **Do** keep every text colour at 4.5:1 or better; `ink-3` is the floor.
- **Do** gate every animation behind `prefers-reduced-motion` and give focus a
  2px accent ring with a page-ground offset.
- **Do** verify `tnum` in-browser before ever changing the typeface.
- **Do** keep `cursor: pointer` on enabled controls. Tailwind v4's preflight
  sets buttons to `cursor: default`; `styles.css` restores it. In a system
  with no shadow, no radius and no raised sheets, the pointer carries more of
  the "this is interactive" signal than it would elsewhere.

### Don't

- **Don't** add a dark theme. The system is light-only, `color-scheme: light`
  is declared, and dark fintech has been rejected twice.
- **Don't** use a shadow, a gradient, a blur, `backdrop-filter`, or a texture.
  There is no elevation vocabulary here.
- **Don't** round anything. `rounded-full` is only for a genuinely circular mark.
- **Don't** introduce a second typeface, a third radius, or a new container width.
- **Don't** tint the accent into a pastel background or use it as a body link
  colour — that is exactly the timid treatment this system was built against.
- **Don't** put green or red on anything unsigned — no green success chips and
  no red category tags. The buy/sell side control inside the order modals is
  the single sanctioned exception (see The Order-Entry Exception); the
  holdings-table row buttons and the cash modal stay neutral.
- **Don't** let the benchmark or an "Other" slice take a series colour; both are
  Chart Neutral by design.
- **Don't** render a modal outside the `ui.tsx` portal — an ancestor `transform`
  from the `.rise` animation traps `position: fixed`.
