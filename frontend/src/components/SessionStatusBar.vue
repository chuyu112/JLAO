<template>
  <section class="status-bar">
    <div class="status-left">
      <n-tag :type="statusType" size="large">{{ statusLabel }}</n-tag>
      <div>
        <div class="panel-title">{{ session?.title || 'JLAO 翡翠直播 Demo' }}</div>
        <div class="transcript-meta">
          平台：{{ session?.platform || '未设置' }} ｜ 主播：{{ session?.anchor_name || '-' }} ｜ 场控：{{
            session?.operator_name || '-'
          }}
        </div>
      </div>
    </div>

    <div class="status-right">
      <n-button size="small" type="success" @click="$emit('loadTab')">
        载入标签页
      </n-button>
      <n-select
        :value="session?.current_product_id || null"
        :options="productOptions"
        size="small"
        style="width: 220px"
        placeholder="选择当前商品"
        @update:value="handleProductChange"
      />
      <n-tag :type="connected ? 'success' : 'warning'">
        {{ connected ? '实时连接正常' : '实时连接未建立' }}
      </n-tag>
      <n-button type="primary" size="small" :disabled="isRunningStatus(session?.status)" @click="$emit('start')">
        <template #icon><play :size="16" /></template>
        载入手机端
      </n-button>
      <n-button size="small" secondary type="error" :disabled="!isRunningStatus(session?.status)" @click="$emit('stop')">
        <template #icon><square :size="16" /></template>
        结束
      </n-button>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { NButton, NSelect, NTag } from 'naive-ui'
import { Play, Square } from 'lucide-vue-next'
import type { LiveSession, Product } from '../types'

const props = defineProps<{
  session: LiveSession | null
  products: Product[]
  connected: boolean
}>()

const emit = defineEmits<{
  start: []
  stop: []
  loadTab: []
  changeProduct: [productId: string]
}>()

const productOptions = computed(() =>
  props.products.map((product) => ({
    label: `${product.name}｜${product.category}`,
    value: product.id,
  })),
)

const statusLabel = computed(() => {
  const status = String(props.session?.status || '')
  if (isRunningStatus(status)) return '手机端已载入'
  if (status === '已结束' || status === '宸茬粨鏉?') return '已结束'
  if (status === '待开始' || status === '寰呭紑濮?') return '待载入'
  return status || '未创建'
})

const statusType = computed(() => {
  const status = String(props.session?.status || '')
  if (isRunningStatus(status)) return 'success'
  if (status === '已结束' || status === '宸茬粨鏉?') return 'default'
  return 'warning'
})

function isRunningStatus(status: unknown) {
  return status === '直播中' || status === '鐩存挱涓?'
}

function handleProductChange(productId: string) {
  emit('changeProduct', productId)
}
</script>
