# Visual System

## Direction

Wikis should feel dark, cinematic, and quiet in the app itself, with restrained pillar color accents.

The reference direction uses:

- deep navy/black backgrounds
- large cream or white typography
- golden Science accents
- colored pillar badges
- immersive topic imagery
- minimal chrome
- bottom navigation with soft glow only for active state

## Core Visual Principle

If the topic has a great Wikipedia image, use it.

If it does not, use a reusable pillar background.

Never let weak source imagery damage the product.

## Image Decision Tree

```text
Wikipedia page has accurate, beautiful image
  -> use topic image

Wikipedia page has accurate but visually weak image
  -> use pillar background

Wikipedia page has only logos, flags, seals, portraits, blurry scans, maps, or documents
  -> use pillar background

Topic is sensitive or easy to misrepresent visually
  -> use pillar background or manually approved asset
```

## Wikipedia Image Selection

The image pipeline should pull candidates from Wikipedia page media, then score them before display.

Use topic media when:

- it clearly represents the topic
- resolution is high enough for a full-screen mobile card
- license and attribution can be stored
- it is not just a logo, flag, seal, coat of arms, blurry scan, or random portrait
- it does not mislead the user about the topic

Store image decision metadata:

```json
{
  "topicId": "black_holes",
  "source": "wikipedia",
  "selectedImageUrl": "https://...",
  "license": "CC BY-SA",
  "attribution": "Author / Wikimedia Commons",
  "qualityScore": 0.91,
  "fallbackUsed": false,
  "rejectionReasons": []
}
```

## Pillar Backgrounds

### Science

Visual motifs:

- stars
- particles
- gravity fields
- orbital lines
- microscopy textures
- dark gradients

Accent:

- gold/yellow

### Literature

Visual motifs:

- ink
- paper texture
- books
- handwritten fragments
- constellations of text

Accent:

- violet

### Society

Visual motifs:

- city grids
- abstract networks
- crowd movement
- institutional geometry
- connected nodes

Accent:

- coral/red

### History

Visual motifs:

- stone
- maps
- parchment
- ruins
- relief carvings
- desert light

Accent:

- blue

## Typography

Recommended iOS-native approach:

- Use San Francisco system font for UI and body.
- Use large, heavy title type for topic names.
- Keep body text readable, not tiny.
- Avoid negative letter spacing.
- Let long titles wrap elegantly.

Hierarchy:

```text
Pillar badge: small, uppercase, semibold
Topic title: very large, bold, 2 to 4 lines allowed
Explanation: readable body, generous line height
Hook label: small but distinct
Hook text: body, slightly emphasized
```

## Layout

The card should feel full-screen.

Avoid:

- nested cards
- visible content boxes around the main explanation
- cluttered category rows
- UI copy explaining gestures
- large search bars

Use:

- subtle top controls
- large title area
- background image or pillar background
- gradient overlays for legibility
- bottom navigation

## Icons

Use simple line icons:

- atom for Science
- book for Literature
- users/network for Society
- column/temple for History
- bookmark for Save
- node graph for Map
- person for Profile

## Accessibility

Requirements:

- Dynamic Type support
- sufficient text contrast over images
- reduce motion mode
- VoiceOver labels for all buttons
- non-gesture alternatives available through options or assistive actions
- no meaning conveyed by color alone
