import { readFile } from 'node:fs/promises'
import { test } from 'node:test'
import assert from 'node:assert/strict'

const ROOT = new URL('../', import.meta.url)

async function readProjectFile(path) {
  return readFile(new URL(path, ROOT), 'utf8')
}

test('live jade recognition does not count low-confidence noise as a detected item', async () => {
  const source = await readProjectFile('frontend/src/components/JadeYoloLivePanel.vue')

  assert.match(source, /DISPLAY_CANDIDATE_MIN_CONFIDENCE = 0\.3/)
  assert.match(source, /DISPLAY_CONFIRMED_MIN_CONFIDENCE = 0\.5/)
  assert.match(source, /const displayDetections = computed/)
  assert.match(source, /isDisplayableDetection/)
  assert.match(source, /const count = displayDetections\.value\.length/)
  assert.match(source, /候选中/)
  assert.match(source, /待确认/)
  assert.match(source, /for \(const detection of displayDetections\.value\)/)
})
