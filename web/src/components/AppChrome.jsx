import {
  Bookmark,
  BookmarkCheck,
  ChevronRight,
  CircleHelp,
  Compass,
  Crosshair,
  ExternalLink,
  Focus,
  GitBranch,
  Minus,
  Plus,
  Search,
  Settings2,
  Share2,
  Sparkles,
  UserRound,
  X,
} from 'lucide-react'
import { PILLARS, TOPIC_CONTENT } from '../data/topicContent.js'

const NAV_ITEMS = [
  { id: 'explore', label: 'Explore', icon: Compass },
  { id: 'trails', label: 'Trails', icon: GitBranch },
  { id: 'saved', label: 'Saved', icon: Bookmark },
]

export function Sidebar({ mode, onModeChange, onHelp }) {
  return (
    <aside className="sidebar" aria-label="Primary navigation">
      <button className="brand" type="button" onClick={() => onModeChange('explore')} aria-label="Wikis home">
        <span className="brand-mark">W</span>
        <span>Wikis</span>
      </button>

      <nav className="sidebar-nav">
        {NAV_ITEMS.map(({ id, label, icon: Icon }) => (
          <button
            className="nav-item"
            data-active={mode === id}
            key={id}
            type="button"
            onClick={() => onModeChange(id)}
          >
            <Icon aria-hidden="true" size={19} strokeWidth={1.7} />
            <span>{label}</span>
          </button>
        ))}
      </nav>

      <div className="sidebar-footer">
        <button className="icon-button rail-action" type="button" onClick={onHelp} aria-label="Show graph tips">
          <CircleHelp size={20} strokeWidth={1.6} />
        </button>
        <button className="icon-button rail-action" type="button" onClick={onHelp} aria-label="Explorer settings">
          <Settings2 size={20} strokeWidth={1.6} />
        </button>
        <button className="avatar-button" type="button" onClick={onHelp} aria-label="Open profile">
          <UserRound size={19} strokeWidth={1.6} />
        </button>
      </div>
    </aside>
  )
}

export function MobileBrand({ onClick }) {
  return (
    <button className="mobile-brand" type="button" onClick={onClick} aria-label="Wikis home">
      <span className="brand-mark">W</span>
      <span>Wikis</span>
    </button>
  )
}

export function ExplorerToolbar({
  query,
  onQueryChange,
  results,
  onSelect,
  filter,
  onFilterChange,
  topicCount,
  onSurprise,
}) {
  return (
    <div className="explorer-toolbar">
      <div className="search-row">
        <div className="search-shell">
          <Search aria-hidden="true" size={20} strokeWidth={1.65} />
          <input
            aria-label="Search topics"
            autoComplete="off"
            value={query}
            onChange={(event) => onQueryChange(event.target.value)}
            placeholder={`Search ${topicCount.toLocaleString()} topics`}
          />
          {query ? (
            <button className="clear-search" type="button" onClick={() => onQueryChange('')} aria-label="Clear search">
              <X size={16} />
            </button>
          ) : null}
          {results.length > 0 ? (
            <div className="search-results" role="listbox" aria-label="Topic results">
              {results.map((node) => {
                const pillar = PILLARS[node.pillar] || PILLARS.society
                return (
                  <button key={node.id} type="button" onClick={() => onSelect(node.id)} role="option">
                    <span className="result-dot" style={{ '--dot-color': pillar.color }} />
                    <span className="result-copy">
                      <strong>{node.label}</strong>
                      <small>{pillar.label}</small>
                    </span>
                    <ChevronRight size={16} strokeWidth={1.6} />
                  </button>
                )
              })}
            </div>
          ) : null}
        </div>
        <button className="surprise-button" type="button" onClick={onSurprise}>
          <Sparkles size={18} strokeWidth={1.6} />
          <span>Surprise me</span>
        </button>
      </div>

      <div className="filters" aria-label="Filter graph by pillar">
        {['all', ...Object.keys(PILLARS)].map((id) => (
          <button
            key={id}
            type="button"
            data-active={filter === id}
            onClick={() => onFilterChange(id)}
          >
            {id === 'all' ? 'All' : PILLARS[id].label}
          </button>
        ))}
      </div>
    </div>
  )
}

export function CanvasControls({ graphRef }) {
  return (
    <div className="canvas-controls" aria-label="Graph controls">
      <button type="button" onClick={() => graphRef.current?.zoomBy(1.2)} aria-label="Zoom in">
        <Plus size={19} strokeWidth={1.6} />
      </button>
      <button type="button" onClick={() => graphRef.current?.zoomBy(0.82)} aria-label="Zoom out">
        <Minus size={19} strokeWidth={1.6} />
      </button>
      <span className="control-divider" />
      <button type="button" onClick={() => graphRef.current?.reset()} aria-label="Fit graph">
        <Focus size={18} strokeWidth={1.6} />
      </button>
      <button type="button" onClick={() => graphRef.current?.reset()} aria-label="Center selected topic">
        <Crosshair size={18} strokeWidth={1.6} />
      </button>
    </div>
  )
}

export function GraphLegend({ stats }) {
  return (
    <div className="graph-legend">
      <div className="legend-pillars">
        {Object.entries(PILLARS).map(([id, pillar]) => (
          <span key={id}>
            <i style={{ '--legend-color': pillar.color }} />
            {pillar.label}
          </span>
        ))}
      </div>
      <span className="legend-divider" />
      <span className="graph-status">
        <i />
        {stats.topics.toLocaleString()} topics · {stats.edges.toLocaleString()} connections
      </span>
    </div>
  )
}

export function TrailBar({ trailNodes, onSelect }) {
  return (
    <div className="trail-bar">
      <span className="trail-label">Recent trail</span>
      <div className="trail-items">
        {trailNodes.map((node, index) => {
          const pillar = PILLARS[node.pillar] || PILLARS.society
          return (
            <span className="trail-segment" key={`${node.id}-${index}`}>
              {index > 0 ? <ChevronRight size={15} strokeWidth={1.6} /> : null}
              <button type="button" onClick={() => onSelect(node.id)}>
                <i style={{ '--trail-color': pillar.color }} />
                {node.label}
              </button>
            </span>
          )
        })}
      </div>
    </div>
  )
}

export function DetailPanel({ node, connected, onSelect, onClose, onContinue, saved, onToggleSaved }) {
  if (!node) return null
  const pillar = PILLARS[node.pillar] || PILLARS.society
  const curated = TOPIC_CONTENT[node.id]
  const title = curated?.title || node.label
  const readingSeconds = curated?.readingSeconds || 18 + ((node.value || 8) % 13)
  const summary = curated?.summary ||
    `${node.label} is part of a web of ideas mapped from the defining links in its Wikipedia introduction.`
  const note = curated?.note ||
    `Explore its ${connected.length || 'closest'} visible connections to see which concepts define its neighborhood.`
  const wikipediaUrl = `https://en.wikipedia.org/wiki/${encodeURIComponent((node.sourceLabel || node.label).replaceAll(' ', '_'))}`

  return (
    <aside className="detail-panel" aria-label={`${title} topic details`}>
      <header className="detail-header">
        <button className="icon-button" type="button" onClick={onToggleSaved} aria-label={saved ? 'Remove from saved' : 'Save topic'}>
          {saved ? <BookmarkCheck size={20} strokeWidth={1.55} /> : <Bookmark size={20} strokeWidth={1.55} />}
        </button>
        <button className="icon-button" type="button" onClick={onClose} aria-label="Close topic details">
          <X size={20} strokeWidth={1.55} />
        </button>
      </header>

      <div className="detail-scroll">
        <h1>{title}</h1>
        <p className="topic-meta">
          <span style={{ color: pillar.color }}>{pillar.label}</span>
          <i />
          {readingSeconds} sec read
        </p>

        {curated?.image ? (
          <img className="topic-image" src={curated.image} alt="Astronomical visualization of a black hole" />
        ) : (
          <div className="topic-constellation" aria-hidden="true" style={{ '--pillar-color': pillar.color }}>
            <span className="constellation-core" />
            <span className="constellation-orbit orbit-one" />
            <span className="constellation-orbit orbit-two" />
          </div>
        )}

        <p className="topic-summary">{summary}</p>
        <p className="topic-note">{note}</p>

        <section className="connections-section">
          <h2>Connected ideas</h2>
          <div className="connection-list">
            {connected.slice(0, 5).map((connectedNode) => {
              const connectedPillar = PILLARS[connectedNode.pillar] || PILLARS.society
              return (
                <button key={connectedNode.id} type="button" onClick={() => onSelect(connectedNode.id)}>
                  <span className="connection-dot" style={{ '--connection-color': connectedPillar.color }} />
                  <span>{TOPIC_CONTENT[connectedNode.id]?.title || connectedNode.label}</span>
                  <ChevronRight size={17} strokeWidth={1.55} />
                </button>
              )
            })}
          </div>
        </section>
      </div>

      <footer className="detail-actions">
        <button className="primary-action" type="button" onClick={onContinue}>
          <Compass size={19} strokeWidth={1.7} />
          Keep exploring
        </button>
        <a className="secondary-action" href={wikipediaUrl} target="_blank" rel="noreferrer">
          <span>Open Wikipedia</span>
          <ExternalLink size={17} strokeWidth={1.55} />
        </a>
      </footer>
    </aside>
  )
}

export function CollectionOverlay({ mode, nodes, onSelect, onClose }) {
  const isSaved = mode === 'saved'
  const title = isSaved ? 'Saved ideas' : 'Your trails'
  const empty = isSaved
    ? 'Save a topic from its reading panel and it will stay here.'
    : 'Your path appears here as you move through the graph.'

  return (
    <section className="collection-overlay" aria-label={title}>
      <div className="collection-heading">
        <div>
          <h1>{title}</h1>
          <p>{isSaved ? 'A private shelf for ideas worth returning to.' : 'Retrace the ideas that pulled you forward.'}</p>
        </div>
        <button className="icon-button" type="button" onClick={onClose} aria-label={`Close ${title.toLowerCase()}`}>
          <X size={20} />
        </button>
      </div>
      {nodes.length ? (
        <div className="collection-list">
          {nodes.map((node, index) => {
            const pillar = PILLARS[node.pillar] || PILLARS.society
            return (
              <button key={`${node.id}-${index}`} type="button" onClick={() => onSelect(node.id)}>
                <span className="collection-number">{String(index + 1).padStart(2, '0')}</span>
                <span className="collection-node" style={{ '--collection-color': pillar.color }} />
                <span className="collection-copy">
                  <strong>{TOPIC_CONTENT[node.id]?.title || node.label}</strong>
                  <small>{pillar.label}</small>
                </span>
                <ChevronRight size={18} strokeWidth={1.55} />
              </button>
            )
          })}
        </div>
      ) : (
        <div className="collection-empty">
          {isSaved ? <Bookmark size={30} strokeWidth={1.3} /> : <GitBranch size={30} strokeWidth={1.3} />}
          <p>{empty}</p>
        </div>
      )}
    </section>
  )
}

export function UtilityToast({ visible, onClose }) {
  if (!visible) return null
  return (
    <div className="utility-toast" role="status">
      <div>
        <strong>Explore the map</strong>
        <span>Drag to pan · Scroll to zoom · Select any node to change focus</span>
      </div>
      <button className="icon-button" type="button" onClick={onClose} aria-label="Dismiss tips">
        <X size={17} />
      </button>
    </div>
  )
}

export function ShareButton({ onShare }) {
  return (
    <button className="share-button" type="button" onClick={onShare} aria-label="Copy this topic link">
      <Share2 size={17} strokeWidth={1.55} />
    </button>
  )
}
