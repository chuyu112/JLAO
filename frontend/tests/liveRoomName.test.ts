declare const require: any

const fs = require('fs')

const sources = [
  'frontend/src/pages/LiveDashboard.vue',
  'frontend/src/pages/ObservationDashboard.vue',
]

for (const path of sources) {
  const source = fs.readFileSync(path, 'utf8')
  if (!source.includes('store.currentSession?.live_room_name')) {
    throw new Error(`${path} should display the live room name detected from the top-left frame region`)
  }
  if (source.includes('翠玉岚珊 珠宝2号店')) {
    throw new Error(`${path} still hardcodes the previous room name 翠玉岚珊 珠宝2号店`)
  }
  if (source.includes('闲值珠宝')) {
    throw new Error(`${path} still contains the old room name 闲值珠宝`)
  }
}

console.log('liveRoomName tests passed')
