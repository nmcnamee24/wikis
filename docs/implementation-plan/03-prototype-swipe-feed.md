# Step 03: Prototype The Swipe Feed

## Goal

Prove the app interaction feels right before connecting the production backend.

The prototype should answer:

- Is the card readable?
- Are gestures intuitive?
- Does the next topic feel satisfying?
- Do Wikipedia images and fallback backgrounds look premium?

## Build

Create a native SwiftUI prototype using the local graph JSON from Step 02.

Screens:

- Feed only at first
- temporary debug overlay allowed

## Tasks

1. Create Xcode project.
2. Load local graph JSON into app models.
3. Build full-screen topic card.
4. Add pillar badge, topic title, explanation, hook, and image/background.
5. Implement swipe down/right/left.
6. Resolve next topic from local graph.
7. Add basic transition animation.
8. Add save button locally.
9. Add debug mode showing selected edge type and reason.
10. Test on iPhone simulator and physical device.

## Acceptance Criteria

- App opens directly to a topic.
- No onboarding is required.
- Down/right/left gestures work.
- Card content fits on common iPhone sizes.
- Long titles wrap cleanly.
- Missing images fall back to pillar backgrounds.
- 20 consecutive swipes do not crash or dead-end.

## Current Implementation

Implemented:

- `Package.swift`
- `Sources/WikisCore/WikisGraph.swift`
- `Sources/WikisCore/GraphNavigator.swift`
- `Sources/WikisCoreSmokeTests/main.swift`
- `App/Wikis/Sources/*.swift`
- `App/Wikis/Resources/seed_graph.json`
- `docs/step-03-swiftui-prototype-usage.md`

Current prototype behavior:

- loads the 100-topic seed graph
- starts on Black Hole
- renders a full-screen SwiftUI topic card
- supports down/right/left drag gestures
- resolves gestures through `GraphNavigator`
- saves topics locally in memory
- records explored topics locally in memory
- includes basic Map and Profile tabs

Verification run:

```text
swift build --product WikisPrototype
swift run WikisCoreSmokeTests data/graph/seed_graph.json
```

Result:

```text
WikisCore smoke test passed
topics: 100
black-hole down: Event horizon
black-hole right: Saturn
black-hole left: Epic of Gilgamesh
```

The local machine does not currently have full Xcode selected, so an iOS simulator run was not possible in this environment.

## Do Not Build Yet

- Real backend calls
- App Store polish
- Account system
- Push notifications
- Search
