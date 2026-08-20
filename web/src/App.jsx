import { useCallback, useDeferredValue, useEffect, useMemo, useRef, useState } from 'react'
import GraphCanvas from './components/GraphCanvas.jsx'
import {
  CanvasControls,
  CollectionOverlay,
  DetailPanel,
  ExplorerToolbar,
  GraphLegend,
  MobileBrand,
  ShareButton,
  Sidebar,
  TrailBar,
  UtilityToast,
} from './components/AppChrome.jsx'
import { buildGraphIndex, getConnectedNodes, topicSearch } from './lib/graph.js'

const START_TOPIC = 'black-hole'

function readStoredIds(key, fallback) {
  try {
    const value = JSON.parse(localStorage.getItem(key) || 'null')
    return Array.isArray(value) ? value : fallback
  } catch {
    return fallback
  }
}

function LoadingState() {
  return (
    <main className="loading-state">
      <span className="brand-mark">W</span>
      <p>Mapping connected ideas…</p>
    </main>
  )
}

function ErrorState({ onRetry }) {
  return (
    <main className="loading-state error-state">
      <span className="brand-mark">W</span>
      <h1>The map could not be opened.</h1>
      <p>The graph data is present, but the browser could not load it.</p>
      <button type="button" onClick={onRetry}>Try again</button>
    </main>
  )
}

export default function App() {
  const [rawGraph, setRawGraph] = useState(null)
  const [loadError, setLoadError] = useState(false)
  const [loadAttempt, setLoadAttempt] = useState(0)
  const [selectedId, setSelectedId] = useState(START_TOPIC)
  const [filter, setFilter] = useState('all')
  const [query, setQuery] = useState('')
  const [mode, setMode] = useState('explore')
  const [detailOpen, setDetailOpen] = useState(true)
  const [helpVisible, setHelpVisible] = useState(false)
  const [shareNotice, setShareNotice] = useState(false)
  const [trail, setTrail] = useState(() => readStoredIds('wikis-trail-v1', [START_TOPIC]))
  const [saved, setSaved] = useState(() => readStoredIds('wikis-saved-v1', []))
  const deferredQuery = useDeferredValue(query)
  const graphRef = useRef(null)

  useEffect(() => {
    const controller = new AbortController()
    setLoadError(false)
    fetch('/data/current-supabase-map.json', { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error(`Graph request failed: ${response.status}`)
        return response.json()
      })
      .then(setRawGraph)
      .catch((error) => {
        if (error.name !== 'AbortError') setLoadError(true)
      })
    return () => controller.abort()
  }, [loadAttempt])

  useEffect(() => {
    localStorage.setItem('wikis-trail-v1', JSON.stringify(trail))
  }, [trail])

  useEffect(() => {
    localStorage.setItem('wikis-saved-v1', JSON.stringify(saved))
  }, [saved])

  const index = useMemo(() => (rawGraph ? buildGraphIndex(rawGraph) : null), [rawGraph])
  const selectedNode = index?.nodesById.get(selectedId)
  const connected = useMemo(
    () => (index ? getConnectedNodes(index, selectedId, 5) : []),
    [index, selectedId],
  )
  const results = useMemo(
    () => (index ? topicSearch(index, deferredQuery, filter) : []),
    [index, deferredQuery, filter],
  )
  const trailNodes = useMemo(
    () => (index ? trail.map((id) => index.nodesById.get(id)).filter(Boolean) : []),
    [index, trail],
  )
  const savedNodes = useMemo(
    () => (index ? saved.map((id) => index.nodesById.get(id)).filter(Boolean) : []),
    [index, saved],
  )

  const selectTopic = useCallback((id) => {
    setSelectedId(id)
    setDetailOpen(true)
    setMode('explore')
    setQuery('')
    setTrail((current) => {
      if (current.at(-1) === id) return current
      return [...current, id].slice(-7)
    })
  }, [])

  const surprise = () => {
    if (!index) return
    const candidates = index.nodes.filter((node) =>
      node.group === 'source' && (filter === 'all' || node.pillar === filter),
    )
    const next = candidates[Math.floor(Math.random() * candidates.length)]
    if (next) selectTopic(next.id)
  }

  const keepExploring = () => {
    const next = connected.find((node) => !trail.includes(node.id)) || connected[0]
    if (next) selectTopic(next.id)
  }

  const toggleSaved = () => {
    setSaved((current) =>
      current.includes(selectedId)
        ? current.filter((id) => id !== selectedId)
        : [selectedId, ...current],
    )
  }

  const shareTopic = async () => {
    const url = new URL(window.location.href)
    url.searchParams.set('topic', selectedId)
    try {
      await navigator.clipboard.writeText(url.toString())
      setShareNotice(true)
      window.setTimeout(() => setShareNotice(false), 1800)
    } catch {
      setHelpVisible(true)
    }
  }

  useEffect(() => {
    const topic = new URLSearchParams(window.location.search).get('topic')
    if (topic && index?.nodesById.has(topic)) selectTopic(topic)
  }, [index, selectTopic])

  if (loadError) return <ErrorState onRetry={() => setLoadAttempt((attempt) => attempt + 1)} />
  if (!index) return <LoadingState />

  return (
    <main className="app-shell" data-panel-open={detailOpen}>
      <Sidebar mode={mode} onModeChange={setMode} onHelp={() => setHelpVisible(true)} />

      <section className="explorer" aria-label="Knowledge graph explorer">
        <MobileBrand onClick={() => setMode('explore')} />
        <ExplorerToolbar
          query={query}
          onQueryChange={setQuery}
          results={results}
          onSelect={selectTopic}
          filter={filter}
          onFilterChange={setFilter}
          topicCount={index.stats.topics}
          onSurprise={surprise}
        />

        <GraphCanvas
          ref={graphRef}
          index={index}
          selectedId={selectedId}
          filter={filter}
          trail={trail}
          onSelect={selectTopic}
        />

        <CanvasControls graphRef={graphRef} />
        <ShareButton onShare={shareTopic} />
        <GraphLegend stats={index.stats} />
        <TrailBar trailNodes={trailNodes} onSelect={selectTopic} />

        {mode !== 'explore' ? (
          <CollectionOverlay
            mode={mode}
            nodes={mode === 'saved' ? savedNodes : trailNodes}
            onSelect={selectTopic}
            onClose={() => setMode('explore')}
          />
        ) : null}

        <UtilityToast visible={helpVisible} onClose={() => setHelpVisible(false)} />
        {shareNotice ? <div className="share-notice" role="status">Topic link copied</div> : null}
      </section>

      {detailOpen ? (
        <DetailPanel
          node={selectedNode}
          connected={connected}
          onSelect={selectTopic}
          onClose={() => setDetailOpen(false)}
          onContinue={keepExploring}
          saved={saved.includes(selectedId)}
          onToggleSaved={toggleSaved}
        />
      ) : null}
    </main>
  )
}
