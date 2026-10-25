export type SystemId = 'battery' | 'drive' | 'optics'
export const systems = {
  battery: {
    index: '01', label: 'Firmware safety', category: 'Software updates', title: 'Authentic,\nnot always safe.',
    short: 'Explore firmware safety',
    description: 'Controllers like the battery manager get firmware updates. A signed update can still misbehave, so AutoShield runs it as a monitored canary.',
    benefit: 'A bad update is rolled back automatically before it can cause harm.',
    image: '/media/battery-blue.png', anchor: { x: 64, y: 72 },
    points: [
      { label: 'Cell sensing', text: 'A sensor that drifts here would mislead the controller. AutoShield compares it with a reference and flags it.', x: 31, y: 42 },
      { label: 'Contactor commands', text: 'A node that floods the bus can starve urgent commands. AutoShield isolates the offender and verifies the fix.', x: 27, y: 55 },
      { label: 'Controller firmware', text: 'New firmware boots in the spare flash bank. If it is unhealthy, the gateway rolls it back.', x: 49, y: 49 },
    ],
  },
  drive: {
    index: '02', label: 'Controller & sensors', category: 'Fault detection', title: 'Silence is\nnot an error.',
    short: 'Explore controller and sensor safety',
    description: 'The drive unit depends on a controller and its sensors. CAN reports no error when either one fails quietly, so AutoShield watches behaviour.',
    benefit: 'Faults are caught, recovered and verified without waiting for the driver.',
    image: '/media/drive-blue.png', anchor: { x: 25, y: 48 },
    points: [
      { label: 'Drive controller', text: 'A hung ECU goes silent. AutoShield notices the missing heartbeat, then restarts it, hard if needed.', x: 32, y: 46 },
      { label: 'Position sensor', text: 'Readings that slowly drift stay valid on the wire. A reference comparison exposes them.', x: 24, y: 49 },
      { label: 'Torque messages', text: 'Flooding by another node delays these messages. AutoShield spots the rate and cuts the offender off.', x: 48, y: 51 },
    ],
  },
  optics: {
    index: '03', label: 'Advanced lenses', category: 'Light & optics', title: 'Light,\nshaped precisely.',
    short: 'Explore the headlamp optics',
    description: 'Inside this concept headlamp, an LED module produces light and a projection lens shapes it into a controlled beam.',
    benefit: 'Precise light distribution helps illuminate the road where it is needed.',
    image: '/media/lenses-blue.png', anchor: { x: 36, y: 60 },
    points: [
      { label: 'Projection lens', text: 'The optical lens directs the light into the designed beam pattern.', x: 32.9, y: 55.7 },
      { label: 'LED module', text: 'The light source sits behind the projection optics.', x: 50.3, y: 57.2 },
      { label: 'Heat sink', text: 'Metal fins dissipate heat from the light-source assembly.', x: 61.9, y: 56.3 },
    ],
  },
} as const
export const systemIds: SystemId[] = ['battery', 'drive', 'optics']
export type HotspotId = SystemId | 'wheels' | 'paint'
export const hotspots: { id: HotspotId; index: string; label: string; anchor: { x: number; y: number }; target: SystemId | null }[] = [
  ...(['battery', 'drive'] as const).map(id => ({ id, index: systems[id].index, label: systems[id].label, anchor: systems[id].anchor, target: id })),
  { id: 'paint', index: '03', label: 'Body colour', anchor: { x: 55, y: 51 }, target: null },
  { id: 'wheels', index: '04', label: 'Wheel design', anchor: { x: 48, y: 71 }, target: null },
]

// Enable each pair only after first/last frames, crop and color have been checked.
export const clips: Record<SystemId, { forward: string; reverse: string; enabled: boolean }> = {
  battery: { forward: '/media/battery-forward.mp4', reverse: '/media/battery-reverse.mp4', enabled: false },
  drive: { forward: '/media/drive-forward.mp4', reverse: '/media/drive-reverse.mp4', enabled: false },
  optics: { forward: '/media/optics-forward.mp4', reverse: '/media/optics-reverse.mp4', enabled: false },
}
