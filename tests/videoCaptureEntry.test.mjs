import { readFile } from 'node:fs/promises'
import { test } from 'node:test'
import assert from 'node:assert/strict'

const ROOT = new URL('../', import.meta.url)

async function readProjectFile(path) {
  return readFile(new URL(path, ROOT), 'utf8')
}

test('capture controls use one start-stop pair across pages', async () => {
  const appTopNav = await readProjectFile('frontend/src/components/AppTopNav.vue')
  const liveDashboard = await readProjectFile('frontend/src/pages/LiveDashboard.vue')
  const observationDashboard = await readProjectFile('frontend/src/pages/ObservationDashboard.vue')
  const statusBar = await readProjectFile('frontend/src/components/SessionStatusBar.vue')
  const yoloPanel = await readProjectFile('frontend/src/components/JadeYoloLivePanel.vue')

  assert.match(appTopNav, /to="\/live"/)
  assert.match(appTopNav, /to="\/observe"/)
  assert.doesNotMatch(appTopNav, /capture video/i)

  assert.match(statusBar, /startButtonLabel = computed\(\(\) =>/)
  assert.match(statusBar, /sourceActive\?: boolean/)
  assert.match(statusBar, /needsVideoSource/)
  assert.doesNotMatch(statusBar, /async function connectVideoSource\(\)/)

  assert.match(liveDashboard, /ref="yoloLivePanel"/)
  assert.match(liveDashboard, /:capture-active="ownVideoCaptureActive"/)
  assert.match(liveDashboard, /:source-active="ownSourceActive"/)
  assert.match(liveDashboard, /:source-blocked="store\.isCaptureModeBlocked\('own'\)"/)
  assert.match(liveDashboard, /@capture-state-change="handleYoloCaptureStateChange"/)
  assert.match(liveDashboard, /store\.activeCaptureMode === 'own'/)
  assert.doesNotMatch(liveDashboard, /async function connectVideoSource\(\)/)
  assert.match(liveDashboard, /yoloLivePanel\.value\?\.stopCapture\(\)/)

  assert.match(observationDashboard, /<jade-yolo-live-panel/)
  assert.match(observationDashboard, /ref="yoloLivePanel"/)
  assert.match(observationDashboard, /:source-active="observeSourceActive"/)
  assert.match(observationDashboard, /:source-blocked="store\.isCaptureModeBlocked\('observe'\)"/)
  assert.match(observationDashboard, /await store\.startScrcpySession\(\)/)
  assert.match(observationDashboard, /await store\.startPhoneCaptureSession\(\)/)
  assert.match(observationDashboard, /await store\.refreshPhoneCaptureStatus\(\)/)
  assert.match(observationDashboard, /store\.activeCaptureMode === 'observe'/)
  assert.doesNotMatch(observationDashboard, /async function connectVideoSource\(\)/)
  assert.match(observationDashboard, /yoloLivePanel\.value\?\.stopCapture\(\)/)

  assert.match(yoloPanel, /startCapture/)
  assert.match(yoloPanel, /stopCapture/)
  assert.match(yoloPanel, /sourceActive\?: boolean/)
  assert.match(yoloPanel, /sourceBlocked\?: boolean/)
  assert.match(yoloPanel, /connectDisabled/)
  assert.match(yoloPanel, /@click="\(\) => stopCapture\(\)"/)
})
