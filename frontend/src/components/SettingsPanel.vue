<template>
  <n-modal
    v-model:show="showModal"
    preset="card"
    title="设置"
    style="width: 600px"
    :mask-closable="false"
  >
    <div class="settings-content">
      <h3 class="settings-section-title">本地 scrcpy 驱动</h3>
      <div class="driver-status">
        <span class="status-label">当前状态：</span>
        <n-tag v-if="drivers.length > 0" type="success">已检测到 {{ drivers.length }} 个驱动</n-tag>
        <n-tag v-else type="warning">未检测到驱动</n-tag>
      </div>

      <div class="driver-list">
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
          </div>
          <n-tag :type="driver.type === 'scrcpy' ? 'info' : 'success'" size="small">
            {{ driver.type === 'scrcpy' ? 'scrcpy' : 'QtScrcpy' }}
          </n-tag>
        </div>
      </div>

      <div class="driver-actions">
        <n-button size="small" secondary :loading="loading" @click="refreshDrivers">
          <template #icon><refresh-cw :size="14" /></template>
          刷新驱动列表
        </n-button>
      </div>

      <div class="manual-path">
        <h4>手动指定路径</h4>
        <n-input
          v-model:value="manualPath"
          placeholder="例如：D:\\scrcpy\\scrcpy.exe"
          size="small"
        />
        <n-button size="small" type="primary" @click="setManualPath">
          使用此路径
        </n-button>
      </div>
    </div>
  </n-modal>

  <n-button size="small" quaternary @click="openSettings">
    <template #icon><settings :size="16" /></template>
    设置
  </n-button>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { NButton, NModal, NTag, NInput } from 'naive-ui'
import { RefreshCw, Settings } from 'lucide-vue-next'
import { useMessage } from 'naive-ui'
import { API_BASE } from '../api/client'

interface ScrcpyDriver {
  name: string
  path: string
  type: string
}

const message = useMessage()
const showModal = ref(false)
const drivers = ref<ScrcpyDriver[]>([])
const selectedPath = ref('')
const loading = ref(false)
const manualPath = ref('')

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
    autoSelectPreferredDriver()
  } catch (error) {
    console.error('读取 scrcpy 驱动失败:', error)
    message.error('读取 scrcpy 驱动失败')
  } finally {
    loading.value = false
  }
}

function autoSelectPreferredDriver() {
  const preferred = drivers.value.find((d) => d.type === 'scrcpy') || drivers.value[0]
  if (preferred) {
    selectedPath.value = preferred.path
  }
}

async function selectDriver(driver: ScrcpyDriver) {
  const appliedPath = await setDriverPath(driver.path)
  if (appliedPath) {
    selectedPath.value = appliedPath
  }
}

async function setManualPath() {
  if (!manualPath.value.trim()) {
    message.error('请输入路径')
    return
  }
  const appliedPath = await setDriverPath(manualPath.value.trim())
  if (appliedPath) {
    selectedPath.value = appliedPath
    manualPath.value = ''
  }
}

async function setDriverPath(path: string): Promise<string | null> {
  try {
    const base = API_BASE || ''
    const response = await fetch(`${base}/api/scrcpy/drivers/select?path=${encodeURIComponent(path)}`, {
      method: 'POST',
      headers: getAuthHeaders(),
    })
    if (response.ok) {
      const data = await response.json() as { path?: string }
      message.success('已设置 scrcpy 驱动')
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

function openSettings() {
  showModal.value = true
  refreshDrivers()
}

onMounted(() => {
  refreshDrivers()
})
</script>

<style scoped>
.settings-content {
  padding: 16px;
}

.settings-section-title {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 12px;
  color: #f4fffc;
}

.driver-status {
  margin-bottom: 16px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-label {
  color: #8fa3b6;
  font-size: 14px;
}

.driver-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 16px;
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

.driver-actions {
  margin-bottom: 16px;
}

.manual-path {
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  padding-top: 16px;
}

.manual-path h4 {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 8px;
  color: #f4fffc;
}

.manual-path .n-input {
  margin-bottom: 8px;
}
</style>
