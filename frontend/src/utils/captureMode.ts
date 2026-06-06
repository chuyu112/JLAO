export type CaptureMode = 'own' | 'observe'

const CAPTURE_MODE_LOCK_KEY = 'jlao-capture-mode-lock'
const CAPTURE_MODE_LOCK_TTL_MS = 12 * 60 * 60 * 1000

export function isModeSwitchLocked(
  activeMode: CaptureMode | null,
  startupMode: CaptureMode | null,
  _currentPath: string,
  targetPath: string,
): boolean {
  const lockedMode = startupMode || activeMode
  const targetMode = routeMode(targetPath)
  return Boolean(lockedMode && targetMode && targetMode !== lockedMode)
}

export function isModeStartBlocked(
  mode: CaptureMode,
  activeMode: CaptureMode | null,
  startupMode: CaptureMode | null,
): boolean {
  const lockedMode = startupMode || activeMode
  return Boolean(lockedMode && lockedMode !== mode)
}

export function readCaptureModeLock(now = Date.now()): CaptureMode | null {
  const storage = getStorage()
  if (!storage) return null

  try {
    const raw = storage.getItem(CAPTURE_MODE_LOCK_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as { mode?: string; updatedAt?: number }
    if (parsed.mode !== 'own' && parsed.mode !== 'observe') {
      storage.removeItem(CAPTURE_MODE_LOCK_KEY)
      return null
    }
    if (typeof parsed.updatedAt !== 'number' || now - parsed.updatedAt > CAPTURE_MODE_LOCK_TTL_MS) {
      storage.removeItem(CAPTURE_MODE_LOCK_KEY)
      return null
    }
    return parsed.mode
  } catch {
    storage.removeItem(CAPTURE_MODE_LOCK_KEY)
    return null
  }
}

export function writeCaptureModeLock(mode: CaptureMode) {
  getStorage()?.setItem(CAPTURE_MODE_LOCK_KEY, JSON.stringify({ mode, updatedAt: Date.now() }))
}

export function clearCaptureModeLock(mode?: CaptureMode) {
  const storage = getStorage()
  if (!storage) return
  if (mode && readCaptureModeLock() !== mode) return
  storage.removeItem(CAPTURE_MODE_LOCK_KEY)
}

function routeMode(path: string): CaptureMode | null {
  if (path.startsWith('/live')) return 'own'
  if (path.startsWith('/observe')) return 'observe'
  return null
}

function getStorage(): Storage | null {
  try {
    return typeof window !== 'undefined' ? window.localStorage : null
  } catch {
    return null
  }
}
