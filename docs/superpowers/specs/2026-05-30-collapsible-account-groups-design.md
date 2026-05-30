# Collapsible account groups in the overview

**Date:** 2026-05-30
**Status:** Approved

## Goal

On the overview page (`/`), let the user collapse and expand individual account
groups by clicking the group heading. A chevron sits left of the heading name:
pointing down (`v`) when expanded, pointing right (`>`) when collapsed. The
chevron animates by rotating 90°, and the accounts slide up into the heading
when collapsing.

## Scope

Collapsing applies **only to groups that have a heading**:

- Named groups from the account-group settings (`heading: <name>`)
- The "ungrouped" pseudo-group (`heading: '__ungrouped__'`)

The legacy "by bank" layout (`heading: null`) is rendered exactly as today — no
chevron, always expanded — because it has no heading row to act as a click
target.

## Persistence

The collapsed state lives in **localStorage**, per device. This was chosen over
DB storage because:

- Collapsing is a frequent, casual view interaction; the existing
  `PUT /account_groups/layout` endpoint is a deliberate, heavy full-layout
  replace and is the wrong tool to fire per click.
- It is conceptually a per-device view preference.
- The "ungrouped" group has no DB row, so a DB column on `account_groups`
  could not represent its state without a special case.

Trade-off accepted: collapsed state does not sync across devices.

## Components

### New module: `src/lib/collapsedGroups.ts`

Modeled on the existing `src/lib/theme.ts` pattern (guarded localStorage access,
read/write helpers, a hook).

- `STORAGE_KEY = 'collapsedGroups'`
- Stores a JSON **array of collapsed group keys** (the `DisplayGroup.key`, e.g.
  `group-123`, `ungrouped`). Semantics: **absent = expanded**. This means new
  groups default to expanded, and a missing/corrupt value degrades safely to an
  empty set (everything expanded), mirroring the `theme` fallback.
- `readCollapsed(): Set<string>` — parse localStorage, tolerate malformed JSON.
- `writeCollapsed(keys: Set<string>): void` — persist as a JSON array.
- `useCollapsedGroups()` — returns `{ isCollapsed(key): boolean, toggle(key): void }`.
  Seeds state from `readCollapsed()` and persists on every change.

### Modified: `src/routes/index.tsx` (`AccountGroupList`)

- Groups with a heading are wrapped in a Radix `Collapsible` (from `radix-ui`,
  already a dependency), with `open = !isCollapsed(group.key)`.
- The heading row becomes a `Collapsible.Trigger` rendered as a full-width
  button (good tap target on mobile): **chevron · name** on the left, **group
  total** on the right.
- The group total stays visible in the collapsed state.
- The accounts `<ul>` goes inside `Collapsible.Content`.
- Groups with `heading: null` render unchanged.

## Animation

- **Chevron:** a single `ChevronRight` (lucide) — shows `>` when collapsed.
  When open, `rotate-90` (points down). `transition-transform duration-200
  ease-in-out`, driven by the trigger/content `data-[state=open]` attribute.
- **Content height:** Radix exposes `--radix-collapsible-content-height`. Two
  keyframes in `index.css` (`collapsible-down` / `collapsible-up`) animate
  height between `0` and that variable; `overflow-hidden` on the content. Same
  duration/easing as the chevron so the motion reads as one gesture.

## Behavior

- First load (no stored value): all groups expanded.
- State survives reload and PWA relaunch (localStorage).

## Testing

- **Unit** (`collapsedGroups`): read/write/toggle round-trips; malformed JSON →
  empty set; absent key → expanded.
- **Component** (`OverviewView`): clicking a heading toggles account visibility;
  `aria-expanded` flips; the group total remains in the DOM when collapsed; the
  legacy by-bank layout exposes no toggle.
