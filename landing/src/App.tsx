import { useEffect, useRef, useState, type CSSProperties } from 'react'
import { ArrowLeft, ArrowRight, ArrowUpRight, Play, Cpu, Palette, Plus, ShieldCheck, X } from 'lucide-react'
import { systems, hotspots, type HotspotId, type SystemId } from './content'
import HoverVideo from './HoverVideo'
import AppearanceMenu from './AppearanceMenu'
import { appearanceOptions, baseExterior, canUseHotspot, type AppearanceMode } from './appearance'

type Phase = 'overview' | 'entering' | 'detail' | 'returning'
const ROOT_IMAGE = '/media/exterior.png'

// Locations calibrated to the approved wide hero crop. The original source
// coordinates remain unchanged for the responsive/mobile layout.
const DESKTOP_ANCHORS: Record<HotspotId, { x: number; y: number }> = {
  drive: { x: 19.1, y: 46.5 },
  battery: { x: 53.4, y: 78.2 },
  paint: { x: 44.9, y: 51.1 },
  wheels: { x: 39.0, y: 75 },
  optics: { x: 36, y: 60 },
}

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
  const demoTimer = useRef<number>()
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
  // The default silver/original choice is already the base car layer. Do not stack a second copy of it over the same pixels.
  const appearanceHasVariant = appearance === 'paint' ? optionId !== 'silver' : appearance === 'wheels' ? optionId !== 'original' : false
  const widePlane = typeof plane.width === 'number' && typeof plane.height === 'number' && plane.width / plane.height > 2
  const displayAnchor = (id: HotspotId, source: { x: number; y: number }) => widePlane ? DESKTOP_ANCHORS[id] : source
  const currentAnchor = displayAnchor(selected, current.anchor)
  const displaySourcePoint = (point: { x: number; y: number }) => widePlane
    ? { x: point.x * .907 - 3.8, y: point.y * 1.326 - 16.3 }
    : point
  const busy = phase === 'entering' || phase === 'returning'

  useEffect(() => {
    const media = matchMedia('(prefers-reduced-motion: reduce)')
    const update = () => setReduced(media.matches)
    update(); media.addEventListener('change', update)
    return () => { media.removeEventListener('change', update); clearTimeout(timer.current); clearTimeout(revealTimer.current); clearTimeout(appearanceTimer.current); clearTimeout(leaveTimer.current); clearTimeout(demoTimer.current); request.current++ }
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
      const { width, height } = element.getBoundingClientRect()
      const mobile = width <= 900
      // The car image and every hotspot continue to share the exact same
      // coordinate plane. Only the plane's placement changes with the layout.
      if (mobile) {
        const w = Math.max(280, width - 32)
        const h = w * 941 / 1672
        const top = width <= 560 ? 316 : 332
        setPlane({ width: w, height: h, left: (width - w) / 2, top })
        return
      }
      // Desktop reference layout: the hero stage is intentionally wide (about
      // 2.62:1), while the car image keeps its own 1672:941 source geometry.
      // Hotspots remain in the existing source-image coordinate system.
      const introWidth = Math.min(390, width * .24)
      const left = introWidth + 28
      const panelWidth = Math.max(320, width - left)
      // Match the wide reference panel while keeping the car and every
      // interactive hotspot on the same responsive coordinate plane.
      const h = Math.min(height * .905, panelWidth / 2.71)
      const w = h * 2.71
      const top = height * .08
      setPlane({ width: w, height: h, left, top })
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

  function navigateToSystem(id: SystemId) {
    if (phase === 'detail') { returnToCar(); return }
    if (phase === 'overview') void transition(id)
  }

  function openAppearanceFromNavigation(mode: AppearanceMode) {
    if (phase === 'detail') { returnToCar(); return }
    openAppearance(mode)
    setAppearancePinned(true)
  }

  function previewDemo() {
    if (phase !== 'overview' || appearance || !ready) return
    clearTimeout(demoTimer.current)
    setHovered('drive')
    // Match the supplied 1.3 s forward hood clip; the existing hover-video
    // component then handles the reverse clip and endpoint lifecycle.
    demoTimer.current = window.setTimeout(() => setHovered(null), reduced ? 0 : 1550)
  }
  useEffect(() => {
    const escape = (event: KeyboardEvent) => { if (event.key === 'Escape') { if (appearance) closeAppearance(); else returnToCar() } }
    window.addEventListener('keydown', escape)
    return () => window.removeEventListener('keydown', escape)
  })

  return <main className={`experience phase-${phase} ${reduced ? 'reduced' : ''}`} style={{ '--scene-width': typeof plane.width === 'number' ? `${plane.width}px` : undefined, '--scene-height': typeof plane.height === 'number' ? `${plane.height}px` : undefined, '--plane-top': typeof plane.top === 'number' ? `${plane.top}px` : undefined } as CSSProperties} aria-busy={busy}>
    <header className="masthead">
      <a className="wordmark" href="/" aria-label="Return to overview">
        <span className="brand-symbol" aria-hidden="true">A<span /></span>
        <span className="brand-copy"><strong>AUTOSHIELD</strong><small>VEHICLE SAFETY SUPERVISOR</small></span>
      </a>
      <nav className="main-nav" aria-label="Main navigation">
        <button className={phase === 'overview' ? 'active' : ''} onClick={() => phase === 'detail' ? returnToCar() : entryButtons.current.drive?.focus({ preventScroll: true })}>Explore</button>
        <button onClick={() => navigateToSystem('drive')}>Systems</button>
        <button onClick={() => navigateToSystem('battery')}>Diagnostics</button>
        <button onClick={() => openAppearanceFromNavigation('paint')}>Appearance</button>
      </nav>
      <div className="header-actions">
        <span className="concept-label"><i aria-hidden="true" />RVCE EL Project</span>
        <a className="live-demo" href="/dashboard/" aria-label="Explore Dashboard"><span>Explore Dashboard</span><ArrowUpRight size={15} aria-hidden="true" /></a>
      </div>
    </header>

    <section ref={stage} className="stage" aria-label="Explore vehicle systems">
      <div className="image-plane" style={{ ...plane, '--focus-x': `${currentAnchor.x}%`, '--focus-y': `${currentAnchor.y}%` } as CSSProperties}>
        <div className="media-envelope"><div className="exterior-envelope">
        <div className="car-visual"><img className="car-image" src={ROOT_IMAGE} alt="Silver electric concept sedan in a studio" draggable={false}/><HoverVideo desired={!appearance && (hovered === 'drive' || hovered === 'battery') ? hovered : null} mode={phase} reduced={reduced} onNeutral={setNeutral}/><div className={`appearance-visual ${appearance && appearanceHasVariant && neutral && !appearanceClosing ? 'shown' : ''}`} aria-hidden="true"><img src={appearanceImage} alt="" draggable={false}/></div></div>
        </div><div className={`detail-visual ${detailVisible ? 'shown' : ''}`}><img className="detail-image" src={current.image} alt={`Illustrative cutaway of the ${current.label.toLowerCase()}`} draggable={false}/></div>
        </div>

        {phase === 'overview' && <div className="vehicle-view-rail" aria-hidden="true">
          <span className="vehicle-view-thumb selected"><img src="/media/reference/view-side.png" alt="" /></span>
          <span className="vehicle-view-thumb top-view"><img src="/media/reference/view-top.png" alt="" /></span>
          <span className="vehicle-view-thumb rear-view"><img src="/media/reference/view-rear.png" alt="" /></span>
        </div>}

        {phase === 'overview' && ready && hotspots.map(item => {
          const { id, target } = item
          const anchor = displayAnchor(id, item.anchor)
          const enabled = canUseHotspot(appearance, id, appearanceClosing)
          if (id === 'paint' || id === 'wheels') return <div key={id} className={`appearance-hotspot ${appearance === id ? 'expanded' : ''}`} style={{ '--anchor-x': `${anchor.x}%`, '--anchor-y': `${anchor.y}%` } as CSSProperties} onPointerEnter={() => openAppearance(id)} onPointerLeave={event => {
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
          return <button key={id} ref={node => { if (target) entryButtons.current[target] = node }} className={`hotspot ${hovered === id ? 'active' : ''}`} style={{ left: `${anchor.x}%`, top: `${anchor.y}%` }} disabled={!enabled} onPointerEnter={() => { if (enabled) setHovered(id) }} onPointerLeave={() => setHovered(null)} onFocus={() => { if (enabled) setHovered(id) }} onBlur={() => setHovered(null)} onClick={target ? () => void transition(target) : undefined} aria-label={target ? systems[target].short : item.label}>
            <span className="hotspot-ring"><Plus size={14} strokeWidth={1.5}/></span><span className="hotspot-label">{item.label}{target && <ArrowUpRight size={15}/>}</span>
          </button>
        })}
        {phase === 'detail' && current.points.map((point, i) => { const position = displaySourcePoint(point); return <button key={point.label} className={`annotation ${annotation === i ? 'open' : ''}`} style={{ left: `${position.x}%`, top: `${position.y}%` }} aria-label={point.label} aria-expanded={annotation === i} onClick={() => setAnnotation(annotation === i ? null : i)}>
          <span>{String(i + 1).padStart(2, '0')}</span><span className="annotation-label">{point.label}</span>
        </button>})}
      </div>

      <div className={`intro ${phase !== 'overview' ? 'hide' : ''}`} aria-hidden={phase !== 'overview'}>
        <p className="eyebrow">REAL-TIME DIAGNOSTICS. SAFER ROADS.</p>
        <h1><span>Valid on</span><span>the <em>wire.</em></span></h1>
        <p className="intro-description">Explore the systems, sensors and intelligence that keep the vehicle safe. Select a point on the car to begin.</p>
        <div className="hero-actions">
          <button className="primary-cta" onClick={() => navigateToSystem('drive')}>Explore Systems <ArrowRight size={16} aria-hidden="true" /></button>
          <button className="demo-cta" onClick={previewDemo}><span className="play-button"><Play size={16} fill="currentColor" strokeWidth={1.5} aria-hidden="true" /></span><span>Watch Demo<small>See it in action</small></span></button>
        </div>
      </div>
      {phase === 'overview' && <div className="scene-prompt"><span>Click on a point<br />to explore.</span></div>}

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
        <button className="feature-note" onClick={() => navigateToSystem('drive')} aria-label="Open controller and sensor safety">
          <span className="feature-index">01</span><span className="feature-icon"><Cpu size={19} strokeWidth={1.5} aria-hidden="true" /></span>
          <span className="feature-copy"><strong>Controller &amp; Sensors</strong><small>Lift the hood. See how a silent ECU or a drifting sensor is caught.</small></span>
          <span className="feature-art controller-art" aria-hidden="true"><img src="/media/reference/controller-module.png" alt="" /></span>
          <span className="feature-arrow"><ArrowRight size={16} aria-hidden="true" /></span>
        </button>
        <button className="feature-note" onClick={() => navigateToSystem('battery')} aria-label="Open firmware safety">
          <span className="feature-index">02</span><span className="feature-icon"><ShieldCheck size={19} strokeWidth={1.5} aria-hidden="true" /></span>
          <span className="feature-copy"><strong>Firmware Safety</strong><small>Look beneath the body. See a bad update judged and rolled back.</small></span>
          <span className="feature-art firmware-art" aria-hidden="true"><img src="/media/battery.png" alt="" /></span>
          <span className="feature-arrow"><ArrowRight size={16} aria-hidden="true" /></span>
        </button>
        <button className="feature-note" onClick={() => openAppearanceFromNavigation('paint')} aria-label="Explore body finishes">
          <span className="feature-index">03</span><span className="feature-icon"><Palette size={19} strokeWidth={1.5} aria-hidden="true" /></span>
          <span className="feature-copy"><strong>Body Finishes</strong><small>Five colours. From studio silver to a vivid electric green.</small></span>
          <span className="finish-stack" aria-hidden="true"><i /><i /><i /><i /><i /></span>
          <span className="feature-arrow"><ArrowRight size={16} aria-hidden="true" /></span>
        </button>
        <button className="feature-note" onClick={() => openAppearanceFromNavigation('wheels')} aria-label="Explore wheel designs">
          <span className="feature-index">04</span><span className="feature-icon wheel-icon"><span aria-hidden="true">◉</span></span>
          <span className="feature-copy"><strong>Wheel Designs</strong><small>Compare multi-spoke, aero and forged wheels.</small></span>
          <span className="feature-art wheel-art" aria-hidden="true"><img src="/media/reference/wheel-closeup.png" alt="" /></span>
          <span className="feature-arrow"><ArrowRight size={16} aria-hidden="true" /></span>
        </button>
      </div>
      <div className="footer-baseline"><span>AutoShield — RVCE EL Project</span><span>{phase === 'overview' ? 'Explore systems. Personalise the exterior.' : 'Illustrative engineering. Concept visualisation.'}</span></div>
    </footer>
    <p className="sr-only" role="status" aria-live="polite">{busy ? `${phase === 'entering' ? 'Opening' : 'Closing'} ${current.label}` : phase === 'detail' ? `${current.label} view. Press Escape to return.` : 'Vehicle overview. Choose a system.'}</p>
    {error && <div className="error-message" role="alert">{error}<button onClick={() => setError('')} aria-label="Dismiss message"><X size={16}/></button></div>}
  </main>
}
