import { forwardRef, memo, useCallback, useEffect, useImperativeHandle, useMemo, useRef } from 'react'
import { PILLARS } from '../data/topicContent.js'
import { getVisibleGraph, layoutVisibleGraph } from '../lib/graph.js'

const TAU = Math.PI * 2
const STAR_COUNT = 180

function seededStars() {
  let seed = 982451653
  const random = () => {
    seed = (seed * 16807) % 2147483647
    return (seed - 1) / 2147483646
  }
  return Array.from({ length: STAR_COUNT }, () => ({
    x: random(),
    y: random(),
    radius: 0.25 + random() * 0.9,
    alpha: 0.14 + random() * 0.58,
  }))
}

const STARS = seededStars()

function roundedRect(ctx, x, y, width, height, radius) {
  ctx.beginPath()
  ctx.roundRect(x, y, width, height, radius)
}

function wrapLabel(ctx, label, maxWidth) {
  const words = label.split(' ')
  const lines = []
  let line = ''
  for (const word of words) {
    const candidate = line ? `${line} ${word}` : word
    if (line && ctx.measureText(candidate).width > maxWidth) {
      lines.push(line)
      line = word
    } else {
      line = candidate
    }
  }
  if (line) lines.push(line)
  return lines.slice(0, 2)
}

const GraphCanvas = memo(forwardRef(function GraphCanvas(
  { index, selectedId, filter, trail, onSelect },
  ref,
) {
  const canvasRef = useRef(null)
  const hostRef = useRef(null)
  const frameRef = useRef(0)
  const drawRef = useRef(() => {})
  const sizeRef = useRef({ width: 900, height: 700, dpr: 1 })
  const viewRef = useRef({ x: 0, y: 0, scale: 1 })
  const pointerRef = useRef({ dragging: false, moved: false, x: 0, y: 0 })
  const hoveredRef = useRef(null)
  const layoutRef = useRef({ nodes: [], edges: [], positions: new Map() })
  const blackHoleImageRef = useRef(null)
  const visible = useMemo(
    () => getVisibleGraph(index, selectedId, filter),
    [index, selectedId, filter],
  )
  const positions = useMemo(
    () => layoutVisibleGraph(visible, selectedId),
    [visible, selectedId],
  )

  layoutRef.current = { ...visible, positions }

  const requestDraw = useCallback(() => {
    cancelAnimationFrame(frameRef.current)
    frameRef.current = requestAnimationFrame(() => drawRef.current())
  }, [])

  const screenPoint = (position) => {
    const { width, height } = sizeRef.current
    const view = viewRef.current
    return {
      x: width / 2 + view.x + position.x * view.scale,
      y: height / 2 + view.y + position.y * view.scale,
    }
  }

  const nodeRadius = (node, ring) => {
    const base = ring === 0 ? 34 : ring === 1 ? 8 + Math.min(node.value || 8, 24) * 0.28 : 6
    return base * Math.max(0.74, Math.min(viewRef.current.scale, 1.25))
  }

  const findNodeAt = (clientX, clientY) => {
    const rect = canvasRef.current.getBoundingClientRect()
    const x = clientX - rect.left
    const y = clientY - rect.top
    const { nodes, positions: currentPositions } = layoutRef.current
    for (let index = nodes.length - 1; index >= 0; index -= 1) {
      const node = nodes[index]
      const position = currentPositions.get(node.id)
      if (!position) continue
      const point = screenPoint(position)
      const radius = nodeRadius(node, position.ring) + 8
      if (Math.hypot(x - point.x, y - point.y) <= radius) return node
    }
    return null
  }

  drawRef.current = function draw() {
    const canvas = canvasRef.current
    if (!canvas) return
    const context = canvas.getContext('2d')
    const { width, height, dpr } = sizeRef.current
    const { nodes, edges, positions: currentPositions } = layoutRef.current
    const view = viewRef.current
    const trailSet = new Set(trail)
    const labelRects = []
    const labeledPoints = []
    const selectedPosition = currentPositions.get(selectedId)
    if (selectedPosition) {
      const selectedPoint = screenPoint(selectedPosition)
      labelRects.push({ x: selectedPoint.x - 110, y: selectedPoint.y + 31, width: 220, height: 52 })
      labeledPoints.push(selectedPoint)
    }

    context.setTransform(dpr, 0, 0, dpr, 0, 0)
    context.clearRect(0, 0, width, height)

    for (const star of STARS) {
      context.beginPath()
      context.fillStyle = `rgba(210, 226, 241, ${star.alpha})`
      context.arc(star.x * width, star.y * height, star.radius, 0, TAU)
      context.fill()
    }

    for (const edge of edges) {
      const from = currentPositions.get(edge.from)
      const to = currentPositions.get(edge.to)
      if (!from || !to) continue
      const start = screenPoint(from)
      const end = screenPoint(to)
      const onSelectedPath = edge.from === selectedId || edge.to === selectedId
      const onTrail = trailSet.has(edge.from) && trailSet.has(edge.to)
      const color = onTrail ? '#f1bc5b' : onSelectedPath ? 'rgba(241,188,91,.52)' : 'rgba(104,137,163,.22)'
      context.beginPath()
      context.strokeStyle = color
      context.lineWidth = (onTrail ? 1.6 : onSelectedPath ? 1.15 : 0.72) * Math.max(0.75, view.scale)
      context.moveTo(start.x, start.y)
      const bend = ((edge.from.length + edge.to.length) % 2 ? 1 : -1) * 11 * view.scale
      context.quadraticCurveTo((start.x + end.x) / 2 + bend, (start.y + end.y) / 2 - bend, end.x, end.y)
      context.stroke()
    }

    const orderedNodes = [...nodes].sort((a, b) => {
      if (a.id === selectedId) return 1
      if (b.id === selectedId) return -1
      return (currentPositions.get(b.id)?.ring || 0) - (currentPositions.get(a.id)?.ring || 0)
    })

    for (const node of orderedNodes) {
      const position = currentPositions.get(node.id)
      if (!position) continue
      const point = screenPoint(position)
      const pillar = PILLARS[node.pillar] || PILLARS.society
      const radius = nodeRadius(node, position.ring)
      const selected = node.id === selectedId
      const hovered = hoveredRef.current === node.id

      context.save()
      if (selected || hovered) {
        context.shadowColor = pillar.color
        context.shadowBlur = selected ? 28 : 15
      }
      context.beginPath()
      context.arc(point.x, point.y, radius + (selected ? 5 : 0), 0, TAU)
      context.fillStyle = selected ? 'rgba(10, 13, 17, .92)' : pillar.soft
      context.fill()
      context.lineWidth = selected ? 1.8 : hovered ? 1.5 : 1
      context.strokeStyle = pillar.color
      context.stroke()

      if (selected && selectedId === 'black-hole' && blackHoleImageRef.current?.complete) {
        context.save()
        context.beginPath()
        context.arc(point.x, point.y, radius - 2, 0, TAU)
        context.clip()
        const image = blackHoleImageRef.current
        const crop = Math.min(image.width, image.height)
        context.drawImage(
          image,
          (image.width - crop) / 2,
          (image.height - crop) / 2,
          crop,
          crop,
          point.x - radius,
          point.y - radius,
          radius * 2,
          radius * 2,
        )
        context.restore()
      } else {
        context.beginPath()
        context.fillStyle = pillar.color
        context.arc(point.x, point.y, selected ? 8 : Math.max(2.2, radius * 0.34), 0, TAU)
        context.fill()
      }
      context.restore()

      const showLabel = selected || position.ring === 1 || hovered || view.scale > 1.2
      if (!showLabel) continue
      context.font = selected
        ? '500 24px Iowan Old Style, Baskerville, Georgia, serif'
        : '500 12px Inter, ui-sans-serif, system-ui, sans-serif'
      context.textAlign = selected ? 'center' : point.x > sizeRef.current.width / 2 ? 'left' : 'right'
      context.textBaseline = 'middle'
      const maxWidth = selected ? 190 : 108
      const lines = wrapLabel(context, node.label, maxWidth)
      const labelX = selected ? point.x : point.x + (point.x > sizeRef.current.width / 2 ? radius + 9 : -radius - 9)
      const labelY = selected ? point.y + radius + 24 : point.y
      const lineHeight = selected ? 24 : 15
      const widest = Math.max(...lines.map((line) => context.measureText(line).width))
      const labelRect = {
        x: context.textAlign === 'left'
          ? labelX - 4
          : context.textAlign === 'right'
            ? labelX - widest - 4
            : labelX - widest / 2 - 4,
        y: labelY - (lines.length * lineHeight) / 2 - 4,
        width: widest + 8,
        height: lines.length * lineHeight + 8,
      }
      const overlaps = labelRects.some((rect) =>
        labelRect.x < rect.x + rect.width &&
        labelRect.x + labelRect.width > rect.x &&
        labelRect.y < rect.y + rect.height &&
        labelRect.y + labelRect.height > rect.y,
      )
      const tooClose = labeledPoints.some((labeledPoint) =>
        Math.hypot(point.x - labeledPoint.x, point.y - labeledPoint.y) < 86,
      )
      if (!selected && !hovered && (overlaps || tooClose)) continue
      if (!selected) {
        labelRects.push(labelRect)
        labeledPoints.push(point)
      }
      if (hovered && !selected) {
        roundedRect(context, labelX + (context.textAlign === 'left' ? -6 : -widest - 6), labelY - 13, widest + 12, lines.length * lineHeight + 10, 5)
        context.fillStyle = 'rgba(7, 12, 19, .9)'
        context.fill()
      }
      context.fillStyle = selected ? '#f4f0e8' : pillar.color
      lines.forEach((line, lineIndex) => {
        const offset = (lineIndex - (lines.length - 1) / 2) * lineHeight
        context.fillText(line, labelX, labelY + offset)
      })
    }
  }

  useEffect(() => {
    const image = new Image()
    image.src = '/images/black-hole.png'
    image.onload = requestDraw
    blackHoleImageRef.current = image
    return () => {
      image.onload = null
    }
  }, [requestDraw])

  useEffect(() => {
    const host = hostRef.current
    const canvas = canvasRef.current
    if (!host || !canvas) return undefined
    const observer = new ResizeObserver(([entry]) => {
      const width = Math.max(1, entry.contentRect.width)
      const height = Math.max(1, entry.contentRect.height)
      const dpr = Math.min(window.devicePixelRatio || 1, 2)
      sizeRef.current = { width, height, dpr }
      canvas.width = Math.round(width * dpr)
      canvas.height = Math.round(height * dpr)
      canvas.style.width = `${width}px`
      canvas.style.height = `${height}px`
      requestDraw()
    })
    observer.observe(host)
    return () => observer.disconnect()
  }, [requestDraw])

  useEffect(() => {
    viewRef.current = { x: 0, y: 12, scale: 1 }
    requestDraw()
  }, [positions, requestDraw])

  useEffect(() => {
    requestDraw()
  }, [trail, requestDraw])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return undefined
    const onWheel = (event) => {
      event.preventDefault()
      const rect = canvas.getBoundingClientRect()
      const mouseX = event.clientX - rect.left - sizeRef.current.width / 2
      const mouseY = event.clientY - rect.top - sizeRef.current.height / 2
      const previous = viewRef.current.scale
      const next = Math.min(2.25, Math.max(0.55, previous * Math.exp(-event.deltaY * 0.001)))
      const ratio = next / previous
      viewRef.current.x = mouseX - (mouseX - viewRef.current.x) * ratio
      viewRef.current.y = mouseY - (mouseY - viewRef.current.y) * ratio
      viewRef.current.scale = next
      requestDraw()
    }
    canvas.addEventListener('wheel', onWheel, { passive: false })
    return () => canvas.removeEventListener('wheel', onWheel)
  }, [requestDraw])

  useImperativeHandle(ref, () => ({
    zoomBy(amount) {
      viewRef.current.scale = Math.min(2.25, Math.max(0.55, viewRef.current.scale * amount))
      requestDraw()
    },
    reset() {
      viewRef.current = { x: 0, y: 12, scale: 1 }
      requestDraw()
    },
  }))

  const onPointerDown = (event) => {
    event.currentTarget.setPointerCapture(event.pointerId)
    pointerRef.current = { dragging: true, moved: false, x: event.clientX, y: event.clientY }
  }

  const onPointerMove = (event) => {
    const pointer = pointerRef.current
    if (pointer.dragging) {
      const dx = event.clientX - pointer.x
      const dy = event.clientY - pointer.y
      if (Math.abs(dx) + Math.abs(dy) > 2) pointer.moved = true
      viewRef.current.x += dx
      viewRef.current.y += dy
      pointer.x = event.clientX
      pointer.y = event.clientY
      requestDraw()
      return
    }
    const hovered = findNodeAt(event.clientX, event.clientY)
    const next = hovered?.id || null
    if (next !== hoveredRef.current) {
      hoveredRef.current = next
      event.currentTarget.style.cursor = hovered ? 'pointer' : 'grab'
      requestDraw()
    }
  }

  const onPointerUp = (event) => {
    const pointer = pointerRef.current
    pointer.dragging = false
    if (!pointer.moved) {
      const node = findNodeAt(event.clientX, event.clientY)
      if (node) onSelect(node.id)
    }
    event.currentTarget.releasePointerCapture(event.pointerId)
  }

  const onPointerLeave = () => {
    hoveredRef.current = null
    pointerRef.current.dragging = false
    requestDraw()
  }

  return (
    <div className="graph-host" ref={hostRef}>
      <canvas
        ref={canvasRef}
        className="graph-canvas"
        role="img"
        aria-label="Interactive knowledge graph. Drag to pan, scroll to zoom, and select a topic to explore it."
        tabIndex="0"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerLeave={onPointerLeave}
      />
      <div className="sr-only" aria-label="Visible topics">
        {visible.nodes.map((node) => (
          <button type="button" key={node.id} onClick={() => onSelect(node.id)}>
            Explore {node.label}
          </button>
        ))}
      </div>
    </div>
  )
}))

export default GraphCanvas
