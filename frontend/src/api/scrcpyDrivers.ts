export interface ScrcpyDriver {
  name: string
  path: string
  type: string
}

export function pickPreferredScrcpyDriver(drivers: ScrcpyDriver[]): ScrcpyDriver | null {
  return drivers.find((driver) => driver.type === 'scrcpy') || drivers[0] || null
}
