import { pickPreferredScrcpyDriver } from '../src/api/scrcpyDrivers'

function assertEqual(actual: string, expected: string) {
  if (actual !== expected) {
    throw new Error(`Expected ${expected}, got ${actual}`)
  }
}

const preferred = pickPreferredScrcpyDriver([
  {
    name: 'QtScrcpy',
    path: 'D:\\QtScrcpy-win-x64-v3.3.3\\QtScrcpy.exe',
    type: 'qtscrcpy',
  },
  {
    name: 'Command line scrcpy',
    path: 'D:\\scrcpy-win64-v4.0\\scrcpy.exe',
    type: 'scrcpy',
  },
])

assertEqual(preferred?.path || '', 'D:\\scrcpy-win64-v4.0\\scrcpy.exe')

console.log('scrcpyDrivers tests passed')
