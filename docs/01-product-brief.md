# Product Brief

## One Sentence

Wikis is a curiosity engine that turns Wikipedia's knowledge graph into a swipeable feed of short, fascinating explanations.

## What It Is

Wikis helps someone learn one idea quickly, then follow curiosity through related, deeper, or unexpected topics.

The product's unique mechanism is not manual content authoring. Wikis pulls source material from the Wikipedia API, condenses each topic with an LLM, chooses an image from the Wikipedia page when it is good enough, and uses Wikipedia link mapping to power related-topic traversal.

The app should feel like opening a window into knowledge for 30 seconds, not starting a course or performing a search.

## What It Is Not

- Not a search engine
- Not a Wikipedia skin
- Not a course platform
- Not social media
- Not a trivia game
- Not an endless short-form retention feed

## Product Promise

Open Wikis and get:

- one topic that owns the screen
- a beautiful or consistent visual environment
- a 20 to 35 second explanation
- a curiosity hook that makes the next swipe feel obvious
- a map of what your curiosity has explored over time

## Primary User

Someone who is curious but does not want to commit to a course, search query, or long article.

Likely usage moments:

- waiting in line
- between meetings
- before bed
- commuting
- replacing a low-value social media check
- following a spontaneous question

## Product Differentiation

Wikipedia is optimized for reference.

Courses are optimized for completion.

Social feeds are optimized for retention.

Wikis is optimized for curiosity.

The key product difference is the source-to-curiosity pipeline:

```text
Wikipedia API source material
  -> LLM-condensed explanation
  -> image selection from Wikipedia media
  -> mapped Wikipedia relationships
  -> gesture-specific traversal engine
```

Wikis must choose the most interesting next topic based on the current topic, user history, graph structure, popularity, novelty, and learning shape.

## V1 Success Definition

V1 succeeds if users can:

- open the app with no setup
- understand the current topic immediately
- learn something complete in under 30 seconds
- swipe naturally without visible instruction labels
- see their explored knowledge accumulating in the map and profile
- trust that topics feel selected, not random sludge

## Non-Goals For V1

- Search
- Comments
- Friends
- Public profiles
- Likes
- Achievements
- Streak pressure
- User-generated topics
- Full article reading
- Desktop/web app
- Complex topic filters

## Core Loop

1. User opens app.
2. Wikis shows a single topic card.
3. User reads a short explanation.
4. User sees a hook.
5. User swipes:
   - Down: continue the rabbit hole
   - Right: stay in the neighborhood
   - Left: teleport somewhere unexpected
6. Exploration is saved to the map and profile.
