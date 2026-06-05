# Step 07: Build The Native iOS App

## Goal

Turn the prototype into a production-quality native iOS app connected to the backend.

## Build

Use:

- Swift
- SwiftUI
- Swift Concurrency
- URLSession typed API clients
- local persistence for cache/history
- XCTest and XCUITest

## Tasks

1. Create production app module structure.
2. Build typed models for topic cards, images, edges, and profile data.
3. Build API client.
4. Implement initial topic fetch.
5. Implement next-topic fetch.
6. Implement image loading and caching.
7. Implement offline topic cache.
8. Implement save topic.
9. Implement polished feed animations.
10. Add accessibility labels.
11. Add Dynamic Type support.
12. Add crash reporting.
13. Add app icon and launch screen.

## Acceptance Criteria

- App launches directly into feed.
- App works with backend topics.
- App continues through prefetched/cached topics during bad network.
- Swipe transitions feel smooth on real devices.
- Accessibility basics pass.
- Crash reporting works.
- No secrets are bundled into the app.

## Do Not Build Yet

- Push notification habit loops
- Public social profile
- Comments
- Likes
- Search, unless needed for internal debugging

