import { PILLAR_OVERRIDES, TOPIC_CONTENT } from '../data/topicContent.js'

const TITLE_META_PATTERN = /Pillar:\s*([^<]+)/i
const QUALITY_PATTERN = /Quality:\s*([^<]+)/i

function cleanLabel(label) {
  return String(label ?? '').replace(/\s+/g, ' ').trim()
}

function parseMeta(node, pattern, fallback) {
  return node.title?.match(pattern)?.[1]?.trim().toLowerCase() || fallback
}

export function buildGraphIndex(raw) {
  const nodes = raw.nodes.map((node) => ({
    ...node,
    sourceLabel: cleanLabel(node.label),
    label: TOPIC_CONTENT[node.id]?.title || cleanLabel(node.label),
    pillar: PILLAR_OVERRIDES[node.id] || parseMeta(node, TITLE_META_PATTERN, 'society'),
    quality: parseMeta(node, QUALITY_PATTERN, 'prototype'),
  }))
  const nodesById = new Map(nodes.map((node) => [node.id, node]))
  const adjacency = new Map(nodes.map((node) => [node.id, []]))

  for (const edge of raw.edges) {
    if (!nodesById.has(edge.from) || !nodesById.has(edge.to)) continue
    const relation = edge.id?.split('__')[1] || 'neighbor'
    const indexedEdge = { ...edge, relation }
    adjacency.get(edge.from).push({ edge: indexedEdge, nodeId: edge.to, direction: 'out' })
    adjacency.get(edge.to).push({ edge: indexedEdge, nodeId: edge.from, direction: 'in' })
  }

  for (const neighbors of adjacency.values()) {
    neighbors.sort((a, b) => {
      const aNode = nodesById.get(a.nodeId)
      const bNode = nodesById.get(b.nodeId)
      const sourceDelta = Number(bNode?.group === 'source') - Number(aNode?.group === 'source')
      return sourceDelta || (bNode?.value || 0) - (aNode?.value || 0)
    })
  }

  return { nodes, nodesById, adjacency, edges: raw.edges, stats: raw.stats }
}

export function getVisibleGraph(index, selectedId, filter = 'all') {
  const visibleIds = new Set([selectedId])
  const parentById = new Map()
  const firstRing = []
  const selectedNeighbors = index.adjacency.get(selectedId) || []
  const matchesFilter = (nodeId) => {
    if (filter === 'all' || nodeId === selectedId) return true
    return index.nodesById.get(nodeId)?.pillar === filter
  }

  for (const item of selectedNeighbors) {
    if (!matchesFilter(item.nodeId) || visibleIds.has(item.nodeId)) continue
    visibleIds.add(item.nodeId)
    parentById.set(item.nodeId, selectedId)
    firstRing.push(item.nodeId)
    if (firstRing.length >= 14) break
  }

  for (const parentId of firstRing) {
    let added = 0
    for (const item of index.adjacency.get(parentId) || []) {
      if (!matchesFilter(item.nodeId) || visibleIds.has(item.nodeId)) continue
      visibleIds.add(item.nodeId)
      parentById.set(item.nodeId, parentId)
      added += 1
      if (added >= 3 || visibleIds.size >= 48) break
    }
    if (visibleIds.size >= 48) break
  }

  const nodes = [...visibleIds].map((id) => index.nodesById.get(id)).filter(Boolean)
  const edges = index.edges.filter((edge) => visibleIds.has(edge.from) && visibleIds.has(edge.to))
  return { nodes, edges, firstRing, parentById }
}

function hashString(value) {
  let hash = 2166136261
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index)
    hash = Math.imul(hash, 16777619)
  }
  return Math.abs(hash >>> 0)
}

export function layoutVisibleGraph(visible, selectedId) {
  const positions = new Map([[selectedId, { x: 0, y: 0, ring: 0 }]])
  const firstCount = Math.max(visible.firstRing.length, 1)
  const goldenAngle = Math.PI * (3 - Math.sqrt(5))

  visible.firstRing.forEach((id, index) => {
    const hash = hashString(id)
    const angle = index * goldenAngle - Math.PI / 2 + ((hash % 17) - 8) * 0.008
    const radius = 195 + (hash % 58)
    positions.set(id, {
      x: Math.cos(angle) * radius,
      y: Math.sin(angle) * radius * 0.78,
      angle,
      ring: 1,
    })
  })

  const childCounts = new Map()
  for (const node of visible.nodes) {
    if (positions.has(node.id)) continue
    const parentId = visible.parentById.get(node.id)
    const parent = positions.get(parentId) || { x: 0, y: 0, angle: 0 }
    const childIndex = childCounts.get(parentId) || 0
    childCounts.set(parentId, childIndex + 1)
    const hash = hashString(node.id)
    const sweep = (childIndex - 1) * 0.42 + ((hash % 11) - 5) * 0.025
    const angle = (parent.angle ?? ((hash % firstCount) * goldenAngle)) + sweep
    const radius = 125 + (hash % 44)
    positions.set(node.id, {
      x: parent.x + Math.cos(angle) * radius,
      y: parent.y + Math.sin(angle) * radius * 0.76,
      angle,
      ring: 2,
    })
  }

  return positions
}

export function getConnectedNodes(index, selectedId, limit = 5) {
  return (index.adjacency.get(selectedId) || [])
    .slice(0, limit)
    .map((item) => ({ ...index.nodesById.get(item.nodeId), relation: item.edge.relation }))
    .filter(Boolean)
}

export function topicSearch(index, query, filter = 'all', limit = 7) {
  const normalized = query.trim().toLowerCase()
  if (!normalized) return []

  const starts = []
  const includes = []
  for (const node of index.nodes) {
    if (filter !== 'all' && node.pillar !== filter) continue
    const label = node.label.toLowerCase()
    if (label.startsWith(normalized)) starts.push(node)
    else if (label.includes(normalized)) includes.push(node)
    if (starts.length >= limit) break
  }
  return [...starts, ...includes].slice(0, limit)
}
