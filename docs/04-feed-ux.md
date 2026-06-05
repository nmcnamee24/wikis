# Feed UX

## Purpose

The feed is the primary product. It should feel like a quiet, cinematic learning surface, not a scrolling list.

## Home State

When the app opens, show one complete topic card.

No onboarding. No search field. No notification prompt. No visible tutorial.

Default first-session card should be broadly fascinating and visually strong, such as:

- Black Holes
- Octopus Intelligence
- The Silk Road
- Pompeii
- The Library of Alexandria
- The Fermi Paradox

## Card Anatomy

Each card uses the same editorial template.

### Pillar

Small, subtle, near the top.

Examples:

- SCIENCE
- LITERATURE
- SOCIETY
- HISTORY

### Topic

Huge typography. This is the hero.

Examples:

- Black Holes
- The Silk Road
- Octopus Intelligence
- The Epic of Gilgamesh

### Explanation

The explanation should take about 20 to 30 seconds to read.

Target length:

- 90 to 140 words for dense topics
- 60 to 100 words for simple topics

Voice:

- clear
- vivid
- specific
- non-academic
- non-childish
- no generic "in today's world" filler

### Curiosity Hook

Always end with one of:

- The weird part:
- Why it matters:
- Scientists still don't know:
- The twist:
- The surprising part:

The hook exists to make the next swipe feel earned.

Example:

```text
The weird part:
Near a black hole, time itself stretches, so two people can disagree about how much time has passed and both be right.
```

## Gestures

### Swipe Down: Continue

Meaning:

Go deeper into the current rabbit hole.

Example:

```text
Black Holes -> Event Horizon -> Spacetime -> Einstein -> Relativity
```

### Swipe Right: Explore

Meaning:

Stay in the neighborhood.

Example:

```text
Black Holes -> Neutron Stars
Black Holes -> Hawking Radiation
Black Holes -> Quasars
```

### Swipe Left: Teleport

Meaning:

Jump somewhere unexpected.

Example:

```text
Black Holes -> Ancient Rome
Black Holes -> The Silk Road
Black Holes -> Octopus Intelligence
```

## Visible Controls

Keep controls minimal:

- Save button
- More/options button
- Bottom tab bar

Avoid visible swipe labels in the main app. The reference concept shows labels for explanation, but the production app should teach gestures through interaction, animation, and possibly a one-time subtle hint after the first card.

## Bottom Navigation

Tabs:

- Home
- Map
- Profile

Home should be visually dominant only when active. Map and Profile are quiet utility surfaces.

## Feed State Machine

```text
AppLaunch
  -> LoadCandidateTopic
  -> RenderTopicCard
  -> UserReads
  -> GestureStarted
  -> ResolveNextTopic
  -> SaveExplorationEvent
  -> AnimateTransition
  -> PrefetchNextCandidates
```

## Error States

If topic loading fails:

- show a cached topic
- allow retry quietly
- never present a technical error on the card surface

If image loading fails:

- use pillar background
- do not show empty frames or broken images

