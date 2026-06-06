import { resolveApiBase } from '../src/api/baseResolver'

const localBase = 'http://127.0.0.1:8000'

function assertEqual(actual: string, expected: string) {
  if (actual !== expected) {
    throw new Error(`Expected ${expected}, got ${actual}`)
  }
}

assertEqual(
  resolveApiBase({
    queryApiBase: '',
    savedApiBase: 'https://jlao.szkakayiduo.com',
    productionShell: true,
    deployedApiBase: 'https://jlao.szkakayiduo.com',
    windowOrigin: 'https://jlao.szkakayiduo.com',
    defaultApiBase: localBase,
  }),
  localBase,
)

assertEqual(
  resolveApiBase({
    queryApiBase: 'http://127.0.0.1:8000',
    savedApiBase: 'https://jlao.szkakayiduo.com',
    productionShell: true,
    deployedApiBase: 'https://jlao.szkakayiduo.com',
    windowOrigin: 'https://jlao.szkakayiduo.com',
    defaultApiBase: localBase,
  }),
  localBase,
)

assertEqual(
  resolveApiBase({
    queryApiBase: '',
    savedApiBase: 'http://47.120.41.143',
    productionShell: true,
    deployedApiBase: 'https://jlao.szkakayiduo.com',
    windowOrigin: 'https://jlao.szkakayiduo.com',
    defaultApiBase: localBase,
  }),
  localBase,
)

assertEqual(
  resolveApiBase({
    queryApiBase: 'https://jlao.szkakayiduo.com',
    savedApiBase: '',
    productionShell: true,
    deployedApiBase: 'https://jlao.szkakayiduo.com',
    windowOrigin: 'https://jlao.szkakayiduo.com',
    defaultApiBase: localBase,
  }),
  localBase,
)

console.log('apiBaseResolver tests passed')
