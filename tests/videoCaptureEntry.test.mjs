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

  assert.match(appTopNav, />其它分析<\/router-link>/)
  assert.match(appTopNav, /aria-disabled="true">其它分析<\/span>/)
  assert.doesNotMatch(appTopNav, /采集视频/)
  assert.match(statusBar, /采集/)
  assert.match(statusBar, /接入视频流/)
  assert.match(statusBar, /停止采集/)
  assert.match(statusBar, /startButtonLabel = computed\(\(\) => '采集'\)/)
  assert.match(statusBar, /sourceActive\?: boolean/)
  assert.match(statusBar, /needsVideoSource/)
  assert.doesNotMatch(statusBar, /开始手机采集|开始观察采集|停止视频流/)
  assert.match(liveDashboard, /ref="yoloLivePanel"/)
  assert.match(liveDashboard, /:capture-active="ownVideoCaptureActive"/)
  assert.match(liveDashboard, /:source-active="ownSourceActive"/)
  assert.match(liveDashboard, /:source-blocked="store\.isCaptureModeBlocked\('own'\)"/)
  assert.match(liveDashboard, /@capture-state-change="handleYoloCaptureStateChange"/)
  assert.match(liveDashboard, /store\.activeCaptureMode === 'own'/)
  assert.match(liveDashboard, /请在视频区域点击“接入视频流”/)
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
  assert.match(observationDashboard, /请在视频区域点击“接入视频流”/)
  assert.doesNotMatch(observationDashboard, /async function connectVideoSource\(\)/)
  assert.match(observationDashboard, /yoloLivePanel\.value\?\.stopCapture\(\)/)
  assert.match(yoloPanel, /接入视频流/)
  assert.match(yoloPanel, /停止视频流/)
  assert.match(yoloPanel, /sourceActive\?: boolean/)
  assert.match(yoloPanel, /sourceBlocked\?: boolean/)
  assert.match(yoloPanel, /connectDisabled/)
  assert.match(yoloPanel, /@click="stopCapture"/)
})
