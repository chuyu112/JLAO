import { readFile } from 'node:fs/promises'
import { test } from 'node:test'
import assert from 'node:assert/strict'

const ROOT = new URL('../', import.meta.url)

async function readProjectFile(path) {
  return readFile(new URL(path, ROOT), 'utf8')
}

test('live jade recognition shows candidates without confirming weak noise', async () => {
  const source = await readProjectFile('frontend/src/components/JadeYoloLivePanel.vue')

  assert.match(source, /DISPLAY_CANDIDATE_MIN_CONFIDENCE = 0\.01/)
  assert.match(source, /DISPLAY_CONFIRMED_MIN_CONFIDENCE = 0\.03/)
  assert.match(source, /const displayDetections = computed/)
  assert.match(source, /const displayCandidates = computed/)
  assert.match(source, /const overlayDetections = computed/)
  assert.match(source, /isDisplayableDetection/)
  assert.match(source, /const count = displayDetections\.value\.length/)
  assert.match(source, /const candidateCount = displayCandidates\.value\.length/)
  assert.match(source, /tracking_state === 'lost'/)
  assert.match(source, /for \(const detection of overlayDetections\.value\)/)
})
