import { useEffect, useRef, useState, type CSSProperties } from 'react'
import { ArrowLeft, ArrowUpRight, Plus, X } from 'lucide-react'
import { systems, hotspots, type HotspotId, type SystemId } from './content'
import HoverVideo from './HoverVideo'
import AppearanceMenu from './AppearanceMenu'
import { appearanceOptions, baseExterior, canUseHotspot, type AppearanceMode } from './appearance'

type Phase = 'overview' | 'entering' | 'detail' | 'returning'
const ROOT_IMAGE = '/media/exterior-polished.png'

export default function App() {
  const [phase, setPhase] = useState<Phase>('overview')
  const [selected, setSelected] = useState<SystemId>('battery')
  const [hovered, setHovered] = useState<HotspotId | null>(null)
  const [annotation, setAnnotation] = useState<number | null>(null)
  const [ready, setReady] = useState(false)
  const [error, setError] = useState('')
  const [reduced, setReduced] = useState(false)
  const [detailVisible, setDetailVisible] = useState(false)
  const [appearance, setAppearance] = useState<AppearanceMode | null>(null)
  const [appearancePinned, setAppearancePinned] = useState(false)
  const [appearanceClosing, setAppearanceClosing] = useState(false)
  const [optionId, setOptionId] = useState('silver')
  const [appearanceImage, setAppearanceImage] = useState(baseExterior)
  const [neutral, setNeutral] = useState(true)
  const [loadedOptions, setLoadedOptions] = useState(() => new Set([baseExterior]))
  const [failedOptions, setFailedOptions] = useState<Set<string>>(() => new Set())
  const optionLoads = useRef(new Set<string>())
  const appearanceTimer = useRef<number>()
  const leaveTimer = useRef<number>()
  const appearanceButtons = useRef<Partial<Record<AppearanceMode, HTMLButtonElement | null>>>({})
  const suppressFocus = useRef(false)
  const lock = useRef(false)
  const request = useRef(0)
  const timer = useRef<number>()
  const revealTimer = useRef<number>()
  const stage = useRef<HTMLElement>(null)
  const [plane, setPlane] = useState<CSSProperties>({})
  const closeButton = useRef<HTMLButtonElement>(null)
  const entryButtons = useRef<Partial<Record<SystemId, HTMLButtonElement | null>>>({})
  const current = systems[selected]
  const busy = phase === 'entering' || phase === 'returning'

  useEffect(() => {
    const media = matchMedia('(prefers-reduced-motion: reduce)')
    const update = () => setReduced(media.matches)
    update(); media.addEventListener('change', update)
    return () => { media.removeEventListener('change', update); clearTimeout(timer.current); clearTimeout(revealTimer.current); clearTimeout(appearanceTimer.current); clearTimeout(leaveTimer.current); request.current++ }
  }, [])

  useEffect(() => {
    if (!appearance) return
    let cancelled = false
    const pending = appearanceOptions[appearance].filter(option => !optionLoads.current.has(option.image))
    pending.forEach(option => {
      optionLoads.current.add(option.image)
      const image = new Image()
      image.onload = () => { image.decode().then(() => {
        if (!cancelled) {
          setLoadedOptions(previous => new Set(previous).add(option.image))
          setFailedOptions(previous => { const next = new Set(previous); next.delete(option.image); return next })
        }
      }).catch(() => { if (!cancelled) setFailedOptions(previous => new Set(previous).add(option.image)) }) }
      image.onerror = () => { if (!cancelled) setFailedOptions(previous => new Set(previous).add(option.image)) }
      image.src = option.image
    })
    return () => { cancelled = true; pending.forEach(option => optionLoads.current.delete(option.image)) }
  }, [appearance])

  function openAppearance(mode: AppearanceMode) {
    if (phase !== 'overview' || !canUseHotspot(appearance, mode, appearanceClosing)) return
    clearTimeout(leaveTimer.current)
    setHovered(null)
    if (appearance === mode) return
    setAppearance(mode); setAppearancePinned(false)
    setOptionId(appearanceOptions[mode][0].id); setAppearanceImage(baseExterior)
  }

  function closeAppearance(restoreFocus = true) {
    if (!appearance || appearanceClosing) return
    const previousMode = appearance
    clearTimeout(leaveTimer.current)
    setAppearanceClosing(true); setHovered(null)
    appearanceTimer.current = window.setTimeout(() => {
      setAppearance(null); setAppearancePinned(false); setAppearanceClosing(false)
      setAppearanceImage(baseExterior)
      if (restoreFocus) {
        suppressFocus.current = true
        appearanceButtons.current[previousMode]?.focus({ preventScroll: true })
        suppressFocus.current = false
      }
    }, reduced ? 0 : 260)
  }

  function chooseAppearance(id: string) {
    if (!appearance || appearanceClosing || !neutral) return
    const option = appearanceOptions[appearance].find(item => item.id === id)
    if (!option || !loadedOptions.has(option.image)) return
    setAppearancePinned(true); setOptionId(id); setAppearanceImage(option.image)
  }

  useEffect(() => {
    const element = stage.current!
    const updatePlane = () => {
      const { width } = element.getBoundingClientRect()
      const mobile = width <= 900
      // Keep the frame, media and hotspots on one unchanged coordinate plane.
      // The shared width also aligns the masthead, title and supporting copy.
      const mediaHeight = Math.max(700, window.innerHeight) - (window.innerHeight <= 780 ? 64 : 76) - 164 - 88
      const w = mobile ? width - 40 : Math.min(width - 2 * Math.min(72, Math.max(24, width * .04)), mediaHeight * 1672 / 941)
      const h = w * 941 / 1672
      setPlane({ width: w, height: h, left: (width - w) / 2, top: mobile ? 132 : 88 })
    }
    const observer = new ResizeObserver(updatePlane)
    observer.observe(element)
    window.addEventListener('resize', updatePlane)
    return () => { observer.disconnect(); window.removeEventListener('resize', updatePlane) }
  }, [])

  useEffect(() => {
    let cancelled = false
    Promise.all([ROOT_IMAGE, systems.battery.image, systems.drive.image].map(source => new Promise<void>((resolve, reject) => {
      const image = new Image()
      image.onload = () => { image.decode().then(resolve, resolve) }
      image.onerror = reject
      image.src = source
    }))).then(() => { if (!cancelled) setReady(true) }).catch(() => { if (!cancelled) setError('An image could not load. Reload to retry.') })
    return () => { cancelled = true }
  }, [])

  function finish(returning: boolean, id = selected) {
    clearTimeout(timer.current)
    setPhase(returning ? 'overview' : 'detail')
    setDetailVisible(!returning)
    lock.current = false
    setTimeout(() => returning ? entryButtons.current[id]?.focus({ preventScroll: true }) : closeButton.current?.focus({ preventScroll: true }), 0)
  }

  function transition(id: SystemId, returning = false) {
    if (id === 'optics' || appearance || lock.current || !ready || (!returning && phase !== 'overview')) return
    lock.current = true
    const token = ++request.current
    setSelected(id); setHovered(null); setAnnotation(null); setError('')
    setPhase(returning ? 'returning' : 'entering')

    // Hover films stay separate from the existing click-to-detail crossfade.
    revealTimer.current = window.setTimeout(() => { if (request.current === token) setDetailVisible(!returning) }, reduced ? 0 : 350)
    timer.current = window.setTimeout(() => { if (request.current === token) finish(returning, id) }, reduced ? 0 : 1250)
  }

  function returnToCar() { if (phase === 'detail') void transition(selected, true) }
  useEffect(() => {
    const escape = (event: KeyboardEvent) => { if (event.key === 'Escape') { if (appearance) closeAppearance(); else returnToCar() } }
    window.addEventListener('keydown', escape)
    return () => window.removeEventListener('keydown', escape)
  })

  return <main className={`experience phase-${phase} ${reduced ? 'reduced' : ''}`} style={{ '--scene-width': typeof plane.width === 'number' ? `${plane.width}px` : undefined, '--scene-height': typeof plane.height === 'number' ? `${plane.height}px` : undefined } as CSSProperties} aria-busy={busy}>
    <header className="masthead">
      <a className="wordmark" href="/" aria-label="Return to overview">AutoShield</a>
      <span className="header-middle">Vehicle safety supervisor</span>
      <span className="concept-label">RVCE EL project</span>
    </header>

    <section ref={stage} className="stage" aria-label="Explore vehicle systems">
      <div className="image-plane" style={{ ...plane, '--focus-x': `${current.anchor.x}%`, '--focus-y': `${current.anchor.y}%` } as CSSProperties}>
        <div className="media-envelope"><div className="exterior-envelope">
        <div className="car-visual"><img className="car-image" src={ROOT_IMAGE} alt="Silver electric concept sedan in a studio" draggable={false}/><HoverVideo desired={!appearance && (hovered === 'drive' || hovered === 'battery') ? hovered : null} mode={phase} reduced={reduced} onNeutral={setNeutral}/><div className={`appearance-visual ${appearance && neutral && !appearanceClosing ? 'shown' : ''}`} aria-hidden="true"><img src={appearanceImage} alt="" draggable={false}/></div></div>
        </div><div className={`detail-visual ${detailVisible ? 'shown' : ''}`}><img className="detail-image" src={current.image} alt={`Illustrative cutaway of the ${current.label.toLowerCase()}`} draggable={false}/></div>
        </div>

        {phase === 'overview' && ready && hotspots.map(item => {
          const { id, target } = item
          const enabled = canUseHotspot(appearance, id, appearanceClosing)
          if (id === 'paint' || id === 'wheels') return <div key={id} className={`appearance-hotspot ${appearance === id ? 'expanded' : ''}`} style={{ '--anchor-x': `${item.anchor.x}%`, '--anchor-y': `${item.anchor.y}%` } as CSSProperties} onPointerEnter={() => openAppearance(id)} onPointerLeave={event => {
            if (!appearancePinned && !event.currentTarget.contains(document.activeElement)) leaveTimer.current = window.setTimeout(() => closeAppearance(false), 140)
          }} onBlur={event => {
            if (!appearancePinned && !event.currentTarget.contains(event.relatedTarget)) closeAppearance(false)
          }}>
            <button ref={node => { appearanceButtons.current[id] = node }} className={`hotspot ${appearance === id ? 'active' : ''}`} disabled={!enabled} onFocus={() => { if (!suppressFocus.current) openAppearance(id) }} onClick={() => {
              if (appearance === id && appearancePinned) closeAppearance()
              else { openAppearance(id); setAppearancePinned(true) }
            }} aria-expanded={appearance === id && !appearanceClosing} aria-controls={`appearance-${id}`} aria-label={item.label}>
              <span className="hotspot-ring">{appearance === id && appearancePinned ? <X size={14} strokeWidth={1.5}/> : <Plus size={14} strokeWidth={1.5}/>}</span>
              <span className="hotspot-label">{id === 'paint' ? 'Paint' : 'Wheels'}</span>
            </button>
            {appearance === id && !appearanceClosing && <span className="menu-bridge" aria-hidden="true"/>}
            {appearance === id && !appearanceClosing && <AppearanceMenu mode={id} selected={optionId} loaded={loadedOptions} unavailable={failedOptions} waiting={!neutral} onSelect={chooseAppearance} onClose={() => closeAppearance()}/>}
          </div>
          return <button key={id} ref={node => { if (target) entryButtons.current[target] = node }} className={`hotspot ${hovered === id ? 'active' : ''}`} style={{ left: `${item.anchor.x}%`, top: `${item.anchor.y}%` }} disabled={!enabled} onPointerEnter={() => { if (enabled) setHovered(id) }} onPointerLeave={() => setHovered(null)} onFocus={() => { if (enabled) setHovered(id) }} onBlur={() => setHovered(null)} onClick={target ? () => void transition(target) : undefined} aria-label={target ? systems[target].short : item.label}>
            <span className="hotspot-ring"><Plus size={14} strokeWidth={1.5}/></span><span className="hotspot-label">{item.label}{target && <ArrowUpRight size={15}/>}</span>
          </button>
        })}
        {phase === 'detail' && current.points.map((point, i) => <button key={point.label} className={`annotation ${annotation === i ? 'open' : ''}`} style={{ left: `${point.x}%`, top: `${point.y}%` }} aria-label={point.label} aria-expanded={annotation === i} onClick={() => setAnnotation(annotation === i ? null : i)}>
          <span>{String(i + 1).padStart(2, '0')}</span><span className="annotation-label">{point.label}</span>
        </button>)}
      </div>

      <div className={`intro ${phase !== 'overview' ? 'hide' : ''}`} aria-hidden={phase !== 'overview'}>
        <h1>Valid on the wire.</h1><p className="intro-description"><span>Wrong in behaviour.</span><span>Select a point to begin.</span></p>
      </div>

      {phase !== 'overview' && <button ref={closeButton} className="back" onClick={returnToCar} disabled={busy} aria-label="Back to vehicle"><ArrowLeft size={18}/><span>{phase === 'returning' ? 'Returning to vehicle' : 'Back to vehicle'}</span><kbd>Esc</kbd></button>}

      <aside className={`detail-copy ${phase === 'detail' ? 'shown' : ''}`} aria-hidden={phase !== 'detail'}>
        <div className="detail-introduction">
        <p className="eyebrow">{current.category}</p><h2>{current.title.split('\n').map(line => <span key={line}>{line}</span>)}</h2>
        <p className="system-description">{current.description}</p>
        </div>
        <div className="detail-components">
        <div className="part-list">{current.points.map((point, i) => <button key={point.label} tabIndex={phase === 'detail' ? 0 : -1} className={annotation === i ? 'selected' : ''} onClick={() => setAnnotation(annotation === i ? null : i)} aria-expanded={annotation === i}>
          <span className="part-row"><small>{String(i+1).padStart(2,'0')}</small>{point.label}<Plus size={14}/></span>{annotation === i && <span className="part-description">{point.text}</span>}
        </button>)}</div>
        <div className="benefit"><span>For the driver</span><p>{current.benefit}</p></div>
        </div>
      </aside>
      {(busy || !ready) && <div className="transition-status"><span className="small-dot"/>{!ready ? 'Preparing the views' : phase === 'returning' ? 'Returning to the exterior' : `Inside the ${current.label.toLowerCase()}`}</div>}
    </section>

    <footer className="scene-footer">
      <div className="feature-notes" aria-label="Ways to explore">
        <div className="feature-note"><h3>Controller &amp; sensors</h3><p>Lift the hood. See how a silent ECU or a drifting sensor is caught.</p></div>
        <div className="feature-note"><h3>Firmware safety</h3><p>Look beneath the body. See a bad update judged and rolled back.</p></div>
        <div className="feature-note"><h3>Body finishes</h3><p>Five colours. From studio silver to a vivid electric green.</p></div>
        <div className="feature-note"><h3>Wheel designs</h3><p>Three expressions. Compare multi-spoke, aero and forged wheels.</p></div>
      </div>
      <div className="footer-baseline"><span>AutoShield — RVCE EL project</span><span>{phase === 'overview' ? 'Explore systems. Personalise the exterior.' : 'Illustrative engineering. Concept visualisation.'}</span></div>
    </footer>
    <p className="sr-only" role="status" aria-live="polite">{busy ? `${phase === 'entering' ? 'Opening' : 'Closing'} ${current.label}` : phase === 'detail' ? `${current.label} view. Press Escape to return.` : 'Vehicle overview. Choose a system.'}</p>
    {error && <div className="error-message" role="alert">{error}<button onClick={() => setError('')} aria-label="Dismiss message"><X size={16}/></button></div>}
  </main>
}
