export const PILLARS = {
  science: { label: 'Science', color: '#f1bc5b', soft: '#3e2f18' },
  culture: { label: 'Culture', color: '#9b78d1', soft: '#281f38' },
  society: { label: 'Society', color: '#ef7d70', soft: '#3b211f' },
  history: { label: 'History', color: '#63a8d1', soft: '#1d3140' },
}

export const PILLAR_OVERRIDES = {
  'black-hole': 'science',
  'event-horizon': 'science',
  'general-relativity': 'science',
  'hawking-radiation': 'science',
  'neutron-star': 'science',
  'stellar-evolution': 'science',
  'electromagnetic-radiation': 'science',
  'gravitational-wave': 'science',
  spacetime: 'science',
  gravity: 'science',
  'albert-einstein': 'science',
  cosmology: 'science',
  'dark-matter': 'science',
  'ancient-greece': 'history',
  'roman-empire': 'history',
  'western-roman-empire': 'history',
  'ada-lovelace': 'science',
  language: 'culture',
  literature: 'culture',
  philosophy: 'culture',
  society: 'society',
  politics: 'society',
}

export const TOPIC_CONTENT = {
  'black-hole': {
    title: 'Black holes',
    readingSeconds: 24,
    summary:
      'A black hole is a region of spacetime where gravity is so strong that nothing—not even light—can escape.',
    note: 'Its boundary, the event horizon, marks the point beyond which every possible path leads inward.',
    image: '/images/black-hole.png',
  },
  'event-horizon': {
    title: 'Event horizon',
    readingSeconds: 21,
    summary:
      'An event horizon is the boundary beyond which events cannot affect an outside observer.',
    note: 'For a black hole, it is not a solid surface—it is a one-way boundary in spacetime.',
  },
  'general-relativity': {
    title: 'General relativity',
    readingSeconds: 28,
    summary:
      'General relativity describes gravity as the curvature of spacetime caused by mass and energy.',
    note: 'Its equations predicted black holes, gravitational waves, and the bending of light.',
  },
  'hawking-radiation': {
    title: 'Hawking radiation',
    readingSeconds: 26,
    summary:
      'Hawking radiation is the faint thermal radiation predicted to be released near a black hole’s event horizon.',
    note: 'Over immense spans of time, that radiation would cause an isolated black hole to evaporate.',
  },
  'neutron-star': {
    title: 'Neutron stars',
    readingSeconds: 23,
    summary:
      'A neutron star is the collapsed core of a massive star, compressed to extraordinary density without becoming a black hole.',
    note: 'A teaspoon of its matter would weigh roughly a billion tons on Earth.',
  },
  'albert-einstein': {
    title: 'Albert Einstein',
    readingSeconds: 25,
    summary:
      'Albert Einstein reshaped modern physics by showing that space, time, matter, and energy are deeply connected.',
    note: 'His general theory of relativity made the geometry of spacetime central to gravity.',
  },
  'ancient-greece': {
    title: 'Ancient Greece',
    readingSeconds: 27,
    summary:
      'Ancient Greece was a network of city-states whose ideas transformed politics, philosophy, art, and science.',
    note: 'Its legacy emerged through exchange and rivalry rather than a single unified nation.',
  },
  'ada-lovelace': {
    title: 'Ada Lovelace',
    readingSeconds: 22,
    summary:
      'Ada Lovelace saw that a general-purpose calculating machine could manipulate symbols as well as numbers.',
    note: 'Her notes on the Analytical Engine contain what is often described as the first published computer program.',
  },
}
