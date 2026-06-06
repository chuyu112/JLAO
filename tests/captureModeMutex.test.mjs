import { readFile } from 'node:fs/promises'
import { test } from 'node:test'
import assert from 'node:assert/strict'

const ROOT = new URL('../', import.meta.url)

async function readProjectFile(path) {
  return readFile(new URL(path, ROOT), 'utf8')
}

test('own and observe capture modes share one persisted mutex', async () => {
  const captureMode = await readProjectFile('frontend/src/utils/captureMode.ts')
  const store = await readProjectFile('frontend/src/stores/jlao.ts')
  const appTopNav = await readProjectFile('frontend/src/components/AppTopNav.vue')
  const liveDashboard = await readProjectFile('frontend/src/pages/LiveDashboard.vue')
  const observationDashboard = await readProjectFile('frontend/src/pages/ObservationDashboard.vue')

  assert.match(captureMode, /CAPTURE_MODE_LOCK_KEY/)
  assert.match(captureMode, /readCaptureModeLock/)
  assert.match(captureMode, /writeCaptureModeLock/)
  assert.match(captureMode, /clearCaptureModeLock/)
  assert.match(captureMode, /targetMode !== lockedMode/)
  assert.doesNotMatch(captureMode, /currentPath !== targetPath/)

  assert.match(store, /readCaptureModeLock\(\)/)
  assert.match(store, /writeCaptureModeLock\(mode\)/)
  assert.match(store, /clearCaptureModeLock\(mode\)/)
  assert.match(store, /isModeStartBlocked\(mode, state\.activeCaptureMode, state\.captureStartupMode\)/)
  assert.match(store, /const persistedMode = readCaptureModeLock\(\)/)

  assert.match(appTopNav, /isModeSwitchLocked\(jlao\.activeCaptureMode, jlao\.captureStartupMode, route\.path, path\)/)
  assert.match(liveDashboard, /:start-disabled="store\.isCaptureModeBlocked\('own'\)"/)
  assert.match(observationDashboard, /:start-disabled="store\.isCaptureModeBlocked\('observe'\)"/)
})
