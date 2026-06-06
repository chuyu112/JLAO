interface ResolveApiBaseOptions {
  queryApiBase: string
  savedApiBase: string
  productionShell: boolean
  deployedApiBase: string
  windowOrigin: string
  defaultApiBase: string
}

function sameOrigin(left: string, right: string) {
  try {
    return new URL(left).origin === new URL(right).origin
  } catch {
    return false
  }
}

function isLoopbackApi(url: string) {
  try {
    const parsed = new URL(url)
    return parsed.hostname === '127.0.0.1' || parsed.hostname === 'localhost'
  } catch {
    return false
  }
}

export function resolveApiBase(options: ResolveApiBaseOptions) {
  if (options.productionShell) {
    if (options.queryApiBase && isLoopbackApi(options.queryApiBase)) return options.queryApiBase
    if (options.savedApiBase && isLoopbackApi(options.savedApiBase)) {
      return options.savedApiBase
    }
    return options.defaultApiBase
  }

  if (options.queryApiBase) return options.queryApiBase
  return options.savedApiBase || options.deployedApiBase || options.defaultApiBase
}
