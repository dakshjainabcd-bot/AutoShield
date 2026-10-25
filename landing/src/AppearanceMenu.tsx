import { Check, X } from 'lucide-react'
import { appearanceOptions, type AppearanceMode } from './appearance'

export default function AppearanceMenu({ mode, selected, loaded, unavailable, waiting, onSelect, onClose }: {
  mode: AppearanceMode; selected: string; loaded: Set<string>; unavailable: Set<string>; waiting: boolean
  onSelect: (id: string) => void; onClose: () => void
}) {
  const options = appearanceOptions[mode]
  const current = options.find(option => option.id === selected)!
  return <div className={`appearance-menu ${mode}`} id={`appearance-${mode}`} role="group" aria-label={mode === 'paint' ? 'Body colour' : 'Wheel design'}>
    <div className="appearance-heading"><span>{mode === 'paint' ? 'Paint' : 'Wheels'}</span><button className="appearance-close" onClick={onClose} aria-label="Close and restore original vehicle"><X size={16} strokeWidth={1.5}/></button></div>
    <div className="appearance-options">
      {options.map(option => <button key={option.id} className={`appearance-option ${option.id === selected ? 'selected' : ''}`} disabled={waiting || !loaded.has(option.image)} aria-label={`${option.label}${unavailable.has(option.image) ? ' — unavailable' : ''}`} aria-pressed={option.id === selected} title={option.label} onClick={() => onSelect(option.id)}>
        {mode === 'paint' ? <span className="paint-chip" style={{ backgroundColor: option.color, color: option.id === 'graphite' ? '#fff' : '#111' }}>{option.id === selected && <Check size={14}/>}</span> : <span className="wheel-chip" style={{ backgroundImage: `url("${option.image}")` }}/>} 
      </button>)}
    </div>
    <div className="appearance-caption" aria-live="polite">{waiting ? 'Returning to exterior…' : current.label}<small>{unavailable.size ? 'Some options could not load' : 'Close to explore other systems'}</small></div>
  </div>
}
