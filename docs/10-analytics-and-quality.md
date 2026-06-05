# Analytics And Quality

## Analytics Philosophy

Analytics should measure whether the app creates satisfying curiosity, not whether it traps users.

Do not optimize blindly for session length. A 30-second session where the user learns something and leaves satisfied is a success.

## Core Product Metrics

### Learning Starts

How often users open the app and see a topic.

### Topic Completion Proxy

Estimated by dwell time relative to reading seconds.

Example:

```text
completion_proxy = dwell_seconds / estimated_reading_seconds
```

Cap at a reasonable threshold so idle sessions do not distort results.

### Curiosity Continuation

How often a user swipes after reading enough of a card.

Segment by gesture:

- down continuation
- right exploration
- left teleport

### Satisfying Exit

A short session can be good if:

- topic was readable
- no errors occurred
- user spent enough time to complete it
- user saved or explored at least one topic

### Topic Quality

Per-topic score based on:

- completion proxy
- saves
- continuation rate
- quick exits
- reports
- source confidence
- editorial rating

## Events

### App Opened

```json
{
  "event": "app_opened",
  "sessionId": "session_123"
}
```

### Topic Viewed

```json
{
  "event": "topic_viewed",
  "topicId": "black_holes",
  "pillar": "science",
  "reasonCode": "starter_pool"
}
```

### Topic Completed Proxy

```json
{
  "event": "topic_completion_proxy",
  "topicId": "black_holes",
  "dwellMs": 26000,
  "readingSeconds": 24
}
```

### Gesture

```json
{
  "event": "gesture",
  "fromTopicId": "black_holes",
  "gesture": "down",
  "toTopicId": "event_horizon",
  "reasonCode": "best_deeper_edge"
}
```

### Saved Topic

```json
{
  "event": "topic_saved",
  "topicId": "black_holes"
}
```

## Quality Checks

Automated content checks:

- reading time within target
- hook prefix present
- title length safe for UI
- source IDs present
- risk level assigned
- image strategy valid
- outgoing edges exist

Editorial checks:

- factual accuracy
- tone
- specificity
- topic sensitivity
- hook quality
- image appropriateness

## Testing

iOS tests:

- feed loads initial topic
- swipe down resolves deeper topic
- swipe right resolves neighbor topic
- swipe left resolves teleport topic
- save persists locally and syncs
- fallback image appears when topic image is missing
- map includes explored topics
- profile distribution updates

Backend tests:

- traversal scorer respects gesture intent
- high-risk unreviewed topics are excluded
- repeated topics are penalized
- fallback candidates are returned
- event ingestion is idempotent

## Production Monitoring

Track:

- API latency
- image load failure rate
- topic load failure rate
- crash-free sessions
- traversal empty-result rate
- content report rate
- cache hit rate

