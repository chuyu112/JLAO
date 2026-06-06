declare const require: any

const fs = require('fs')

const source = fs.readFileSync('frontend/src/components/LiveSourcePanel.vue', 'utf8')

if (source.includes('getUserMedia')) {
  throw new Error('LiveSourcePanel must not request microphone input with getUserMedia')
}

if (source.includes('startAudioInputCapture')) {
  throw new Error('LiveSourcePanel must not expose microphone audio input capture')
}

console.log('noMicrophoneCapture tests passed')
