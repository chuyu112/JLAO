<template>
  <section class="panel">
    <header class="panel-header">
      <div>
        <div class="panel-title">虚拟场控沙盘</div>
        <div class="transcript-meta">仅模拟，不发送 · 主播补充、用户问题、风险改写</div>
      </div>
      <n-tag size="small" type="success">{{ suggestions.length }} 条</n-tag>
    </header>

    <div class="panel-body">
      <div v-if="suggestions.length === 0" class="empty-state">
        JLAO 会根据公开视频号直播观察生成平台外虚拟回复。
      </div>
      <div v-else class="suggestion-list">
        <article
          v-for="item in suggestions"
          :key="item.id"
          class="suggestion-card"
          :class="{ 'high-risk': item.risk_level === '高' }"
        >
          <div class="suggestion-head">
            <div class="suggestion-type">
              <alert-triangle v-if="item.type === '风险提醒' || item.type === '风险改写'" :size="16" />
              <message-square-text v-else :size="16" />
              {{ item.type }}
            </div>
            <div class="status-right">
              <n-tag size="small" :type="riskTagType(item.risk_level)">风险：{{ item.risk_level }}</n-tag>
              <n-tag size="small">{{ item.status }}</n-tag>
            </div>
          </div>
          <div class="suggestion-content">{{ item.content }}</div>
          <div class="suggestion-reason">原因：{{ item.reason }}</div>
          <div class="suggestion-actions">
            <n-button size="tiny" type="primary" secondary @click="$emit('accept', item.id)">
              <template #icon><check :size="14" /></template>
              标记可用
            </n-button>
            <n-button size="tiny" secondary @click="copyText(item)">
              <template #icon><copy :size="14" /></template>
              复制
            </n-button>
            <n-button size="tiny" type="success" secondary @click="$emit('used', item.id)">
              <template #icon><check-check :size="14" /></template>
              加入样本
            </n-button>
            <n-button size="tiny" type="error" secondary @click="$emit('reject', item.id)">
              <template #icon><x :size="14" /></template>
              拒绝
            </n-button>
          </div>
        </article>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { NButton, NTag, useMessage } from 'naive-ui'
import { AlertTriangle, Check, CheckCheck, Copy, MessageSquareText, X } from 'lucide-vue-next'
import type { Suggestion } from '../types'

defineProps<{
  suggestions: Suggestion[]
}>()

const emit = defineEmits<{
  accept: [id: string]
  copy: [id: string]
  used: [id: string]
  reject: [id: string]
}>()

const message = useMessage()

function riskTagType(level: string) {
  if (level === '高') return 'error'
  if (level === '中') return 'warning'
  return 'success'
}

async function copyText(item: Suggestion) {
  await navigator.clipboard.writeText(item.content)
  emit('copy', item.id)
  message.success('已复制虚拟回复')
}
</script>

