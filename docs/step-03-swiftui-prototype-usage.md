# Step 03 SwiftUI Prototype Usage

## Purpose

This step creates the first native app prototype that loads the local seed graph and renders Wikis as a swipe feed.

## Current Structure

```text
Sources/WikisCore/
  Graph models and navigation logic

Sources/WikisCoreSmokeTests/
  Executable smoke test for graph decoding and navigation

App/Wikis/Sources/
  SwiftUI prototype app

App/Wikis/Resources/
  seed_graph.json copied from data/graph/seed_graph.json
```

## Build Core And Prototype

```bash
swift build --product WikisPrototype
```

## Run Graph Smoke Test

```bash
swift run WikisCoreSmokeTests data/graph/seed_graph.json
```

Expected result:

```text
WikisCore smoke test passed
topics: 100
black-hole down: Event horizon
black-hole right: Neutron star
black-hole left: Silk Road
```

## Xcode Note

The current machine has Apple Command Line Tools active, not full Xcode:

```text
xcodebuild requires Xcode, but active developer directory is CommandLineTools
```

Because of that, the iOS simulator build was not run here. The SwiftUI source and core package compile with the installed Swift toolchain.

To run the prototype on iPhone simulator, open the real iOS project:

```bash
open WikisPrototype.xcodeproj
```

Then select:

```text
Scheme: WikisPrototype
Destination: any iPhone simulator
```

Do not run the Swift Package executable target on an iPhone simulator. That can crash with a missing bundle identifier because it is not packaged as a real iOS app bundle.

## Current Prototype Features

- loads `seed_graph.json`
- starts on Black Hole
- renders full-screen topic card
- displays pillar, title, explanation, hook, image/fallback background
- supports save button locally
- swipe down/right/left maps to graph gestures
- includes basic Map and Profile tabs backed by local exploration history
