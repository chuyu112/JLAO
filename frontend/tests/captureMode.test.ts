import { isModeStartBlocked, isModeSwitchLocked } from '../src/utils/captureMode'

function assertTrue(value: boolean, message: string) {
  if (!value) {
    throw new Error(message)
  }
}

function assertFalse(value: boolean, message: string) {
  if (value) {
    throw new Error(message)
  }
}

assertTrue(
  isModeSwitchLocked('own', null, '/live', '/observe'),
  'observe nav should be locked while own mode is active',
)
assertFalse(
  isModeSwitchLocked('own', null, '/live', '/live'),
  'current mode nav should remain available while own mode is active',
)
assertTrue(
  isModeStartBlocked('observe', 'own', null),
  'observe start should be blocked while own mode is active',
)
assertTrue(
  isModeStartBlocked('own', null, 'observe'),
  'own start should be blocked while observe mode is starting',
)
assertFalse(
  isModeStartBlocked('observe', null, null),
  'observe start should be available when no mode is active',
)

console.log('captureMode tests passed')
