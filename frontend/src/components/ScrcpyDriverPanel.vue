<template>
  <section class="panel scrcpy-driver-panel">
    <header class="panel-header">
      <div>
        <div class="panel-title">本地 scrcpy 驱动</div>
        <div class="transcript-meta">自动检测 D 盘根目录下的命令行 scrcpy</div>
      </div>
    </header>

    <div class="panel-body">
      <div v-if="drivers.length > 0" class="driver-list">
        <div
          v-for="driver in drivers"
          :key="driver.path"
          class="driver-item"
          :class="{ active: selectedPath === driver.path }"
          @click="selectDriver(driver)"
        >
          <div class="driver-info">
            <strong>{{ driver.name }}</strong>
            <span class="driver-path">{{ driver.path }}</span>
            <span v-if="selectedPath === driver.path" class="driver-status">已自动使用</span>
          </div>
          <n-tag :type="driver.type === 'scrcpy' ? 'info' : 'success'" size="small">
            {{ driver.type === 'scrcpy' ? 'scrcpy' : 'QtScrcpy' }}
          </n-tag>
        </div>
      </div>

      <div v-else class="empty-state compact">
        未检测到 D:\scrcpy-win64-v4.0\scrcpy.exe
      </div>

      <n-button size="small" secondary :loading="loading" @click="refreshDrivers">
        <template #icon><refresh-cw :size="14" /></template>
        刷新驱动列表
      </n-button>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { NButton, NTag } from 'naive-ui'
import { RefreshCw } from 'lucide-vue-next'
import { useMessage } from 'naive-ui'
import { API_BASE } from '../api/client'
import { pickPreferredScrcpyDriver, type ScrcpyDriver } from '../api/scrcpyDrivers'

const message = useMessage()

const drivers = ref<ScrcpyDriver[]>([])
const selectedPath = ref('')
const loading = ref(false)

function getAuthHeaders(): Record<string, string> {
  const token = localStorage.getItem('jlao_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function refreshDrivers() {
  loading.value = true
  try {
    const base = API_BASE || ''
    const response = await fetch(`${base}/api/scrcpy/drivers`, {
      headers: getAuthHeaders(),
    })
    if (!response.ok) {
      message.error('读取 scrcpy 驱动失败')
      return
    }

    drivers.value = await response.json() as ScrcpyDriver[]
    await autoSelectPreferredDriver()
  } catch (error) {
    console.error('读取 scrcpy 驱动失败:', error)
    message.error('读取 scrcpy 驱动失败')
  } finally {
    loading.value = false
  }
}

async function autoSelectPreferredDriver() {
  const preferred = pickPreferredScrcpyDriver(drivers.value)
  if (!preferred) {
    selectedPath.value = ''
    return
  }

  const appliedPath = await setDriverPath(preferred.path, { silentSuccess: true })
  if (appliedPath) {
    selectedPath.value = appliedPath
  }
}

async function selectDriver(driver: ScrcpyDriver) {
  const appliedPath = await setDriverPath(driver.path)
  if (appliedPath) {
    selectedPath.value = appliedPath
  }
}

async function setDriverPath(
  path: string,
  options: { silentSuccess?: boolean } = {},
): Promise<string | null> {
  try {
    const base = API_BASE || ''
    const response = await fetch(`${base}/api/scrcpy/drivers/select?path=${encodeURIComponent(path)}`, {
      method: 'POST',
      headers: getAuthHeaders(),
    })
    if (response.ok) {
      const data = await response.json() as { path?: string }
      if (!options.silentSuccess) {
        message.success('已使用该 scrcpy 驱动')
      }
      return data.path || path
    }

    const err = await response.json().catch(() => null) as { detail?: string } | null
    message.error('设置 scrcpy 驱动失败: ' + (err?.detail || response.statusText))
  } catch (error) {
    console.error('设置 scrcpy 驱动失败:', error)
    message.error('设置 scrcpy 驱动失败')
  }
  return null
}

onMounted(() => {
  refreshDrivers()
})
</script>

<style scoped>
.scrcpy-driver-panel {
  min-height: 0;
}

.driver-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 12px;
}

.driver-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 10px 12px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.04);
  cursor: pointer;
  transition: background 0.2s, border-color 0.2s;
}

.driver-item:hover {
  background: rgba(255, 255, 255, 0.08);
}

.driver-item.active {
  border-color: rgba(34, 211, 166, 0.55);
  background: rgba(34, 211, 166, 0.1);
}

.driver-info {
  display: flex;
  flex: 1;
  min-width: 0;
  flex-direction: column;
  gap: 4px;
}

.driver-info strong {
  color: #f4fffc;
  font-size: 13px;
}

.driver-path {
  color: #8fa3b6;
  font-size: 11px;
  word-break: break-all;
}

.driver-status {
  color: #22d3a6;
  font-size: 11px;
}
</style>
