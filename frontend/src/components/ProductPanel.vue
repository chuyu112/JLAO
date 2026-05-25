<template>
  <section class="panel">
    <header class="panel-header">
      <div>
        <div class="panel-title">当前商品</div>
        <div class="transcript-meta">商品资料会参与 AI 建议生成</div>
      </div>
      <n-tag v-if="product" size="small" type="success">{{ product.category }}</n-tag>
      <n-tag v-else-if="manualName" size="small" type="warning">手动矫正</n-tag>
    </header>

    <div class="panel-body">
      <div v-if="!product && !manualName" class="empty-state">暂无商品，请先选择当前直播商品。</div>
      <div v-else-if="!product && manualName">
        <dl class="product-kv">
          <dt>名称</dt>
          <dd>{{ manualName }}</dd>
        </dl>
      </div>
      <template v-else-if="product">
        <dl class="product-kv">
          <dt>名称</dt>
          <dd>{{ product.name }}</dd>
          <dt>种水</dt>
          <dd>{{ product.water }}</dd>
          <dt>颜色</dt>
          <dd>{{ product.color }}</dd>
          <dt>尺寸</dt>
          <dd>{{ product.size }}</dd>
          <dt>证书</dt>
          <dd>{{ product.certificate }}</dd>
          <dt>瑕疵</dt>
          <dd>{{ product.flaws }}</dd>
          <dt>价格</dt>
          <dd>{{ product.price ? `¥${product.price.toLocaleString('zh-CN')}` : '未设置' }}</dd>
        </dl>

        <div class="tag-row">
          <n-tag v-for="point in product.selling_points" :key="point" size="small" type="success" round>
            {{ point }}
          </n-tag>
        </div>

        <n-divider />

        <div class="panel-title">注意事项</div>
        <p class="transcript-text">{{ product.cautions || '暂无注意事项' }}</p>

        <div class="panel-title" style="margin-top: 14px">常见问题</div>
        <div class="tag-row">
          <n-tag v-for="question in product.faq" :key="question" size="small">
            {{ question }}
          </n-tag>
        </div>
      </template>

      <n-divider />

      <div class="detected-dimensions-section">
        <div class="panel-title" style="margin-bottom: 8px">AI 实时识别</div>
        <dl class="product-kv">
          <dt>颜色</dt>
          <dd>{{ detectedColor || '—' }}</dd>
          <dt>种水</dt>
          <dd>{{ detectedWater || '—' }}</dd>
          <dt>题材</dt>
          <dd>{{ detectedSubject || '—' }}</dd>
          <dt>附加</dt>
          <dd>{{ detectedExtra || '—' }}</dd>
        </dl>
        <div v-if="detectedFullName" class="detected-full-name">
          {{ detectedFullName }}
        </div>
      </div>

      <n-divider />

      <div class="manual-correct-section">
        <div class="panel-title" style="margin-bottom: 8px">手动矫正</div>
        <div v-if="!manualName" class="manual-correct-row">
          <n-input
            v-model:value="manualInput"
            size="small"
            placeholder="输入真实货品名称"
            style="flex: 1"
            @keydown.enter="handleManual"
          />
          <n-button size="small" type="warning" @click="handleManual">矫正</n-button>
        </div>
        <div v-else class="manual-correct-row">
          <n-tag size="small" type="warning">手动: {{ manualName }}</n-tag>
          <n-button size="small" @click="handleClearManual">恢复自动</n-button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { NButton, NDivider, NInput, NTag } from 'naive-ui'
import type { Product } from '../types'

const props = defineProps<{
  product: Product | null
  manualName?: string
  detectedColor?: string
  detectedWater?: string
  detectedSubject?: string
  detectedExtra?: string
  detectedFullName?: string
}>()

const emit = defineEmits<{
  setManualProductName: [name: string]
}>()

const manualInput = ref('')

function handleManual() {
  const name = manualInput.value.trim()
  if (name) {
    emit('setManualProductName', name)
    manualInput.value = ''
  }
}

function handleClearManual() {
  emit('setManualProductName', '')
}
</script>
