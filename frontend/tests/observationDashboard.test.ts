import fs from 'node:fs'

const source = fs.readFileSync('frontend/src/pages/ObservationDashboard.vue', 'utf8')
const yoloPanelSource = fs.readFileSync('frontend/src/components/JadeYoloLivePanel.vue', 'utf8')
const statusBarSource = fs.readFileSync('frontend/src/components/SessionStatusBar.vue', 'utf8')
const globalCss = fs.readFileSync('frontend/src/styles/global.css', 'utf8')

function assertIncludes(text: string, expected: string) {
  if (!text.includes(expected)) {
    throw new Error(`Expected ObservationDashboard.vue to include ${expected}`)
  }
}

function assertNotIncludes(text: string, unexpected: string) {
  if (text.includes(unexpected)) {
    throw new Error(`Expected ObservationDashboard.vue not to include ${unexpected}`)
  }
}

assertIncludes(source, '<scrcpy-driver-panel')
assertIncludes(source, "import ScrcpyDriverPanel from '../components/ScrcpyDriverPanel.vue'")
assertIncludes(source, '<jade-yolo-live-panel')
assertIncludes(source, "import JadeYoloLivePanel from '../components/JadeYoloLivePanel.vue'")
assertIncludes(source, 'ref="yoloLivePanel"')
assertIncludes(source, ':capture-active="observeCaptureActive"')
assertIncludes(source, '@capture-state-change="handleYoloCaptureStateChange"')
assertIncludes(source, 'const yoloLivePanel = ref<InstanceType<typeof JadeYoloLivePanel> | null>(null)')
assertIncludes(source, 'const observeCaptureActive = ref(false)')
assertIncludes(source, 'const captured = await yoloLivePanel.value?.startCapture()')
assertIncludes(source, 'observeCaptureActive.value = true')
assertIncludes(source, 'observeCaptureActive.value = false')
assertIncludes(source, 'function handleYoloCaptureStateChange(active: boolean)')
assertIncludes(source, '@start-stt="store.connectStt"')
assertIncludes(source, '@audio-frame="store.sendSttAudio"')
assertNotIncludes(source, 'await store.startScrcpySession()')
assertNotIncludes(source, 'await store.startPhoneCaptureSession()')
assertNotIncludes(source, 'await store.startNativeSttSession()')
assertIncludes(yoloPanelSource, '复制视频流 YOLO识别')
assertIncludes(yoloPanelSource, '接入视频流')
assertIncludes(yoloPanelSource, 'captureStateChange: [active: boolean]')
assertIncludes(yoloPanelSource, "emit('captureStateChange', true)")
assertIncludes(yoloPanelSource, "emit('captureStateChange', false)")
assertIncludes(yoloPanelSource, 'defineExpose({ startCapture, stopCapture })')
assertIncludes(statusBarSource, '接入视频流')
assertIncludes(statusBarSource, '停止视频流')
assertIncludes(statusBarSource, 'captureActive?: boolean')
assertIncludes(statusBarSource, 'captureRunning')
assertIncludes(statusBarSource, 'props.captureActive')
assertIncludes(globalCss, 'grid-template-rows: minmax(86px, auto) minmax(300px, 1.55fr)')
assertIncludes(globalCss, 'height: auto;')
assertIncludes(globalCss, 'justify-content: flex-end;')

console.log('observationDashboard tests passed')
