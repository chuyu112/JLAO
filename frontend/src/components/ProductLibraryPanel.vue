<template>
  <section class="panel product-library-panel">
    <header class="panel-header">
      <div>
        <div class="panel-title">商品库</div>
        <div class="transcript-meta">{{ products.length }} 个商品 · 当前识别 {{ detectedName || '待识别' }}</div>
      </div>
      <n-tag size="small" type="success">{{ currentProduct?.category || '商品' }}</n-tag>
    </header>

    <div class="panel-body product-library-body">
      <article
        v-for="product in visibleProducts"
        :key="product.id"
        class="product-library-card"
        :class="{ active: product.id === currentProductId }"
        @click="$emit('select-product', product.id)"
      >
        <div class="product-library-head">
          <strong>{{ product.name }}</strong>
          <span>{{ product.category }}</span>
        </div>
        <p>{{ product.water }} · {{ product.color }} · {{ product.size }}</p>
        <small>{{ product.selling_points.slice(0, 2).join(' / ') || product.cautions || '暂无卖点' }}</small>
      </article>

      <div v-if="!products.length" class="empty-state compact">商品库暂无数据。</div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { NTag } from 'naive-ui'
import type { Product } from '../types'

const props = defineProps<{
  products: Product[]
  currentProductId: string | null
  detectedName?: string
}>()

defineEmits<{
  'select-product': [id: string]
}>()

const currentProduct = computed(() => props.products.find((item) => item.id === props.currentProductId) || props.products[0])
const visibleProducts = computed(() => props.products.slice(0, 8))
</script>

<style scoped>
.product-library-panel {
  min-height: 0;
}

.product-library-body {
  display: grid;
  gap: 8px;
}

.product-library-card {
  min-height: 74px;
  padding: 9px 10px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.04);
  cursor: pointer;
}

.product-library-card.active {
  border-color: rgba(34, 211, 166, 0.55);
  background: rgba(34, 211, 166, 0.1);
}

.product-library-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.product-library-head strong {
  overflow: hidden;
  color: #f4fffc;
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.product-library-head span,
.product-library-card small {
  color: #8fa3b6;
  font-size: 11px;
  white-space: nowrap;
}

.product-library-card p {
  margin: 6px 0 4px;
  color: #c6d3df;
  font-size: 12px;
  line-height: 1.35;
}
</style>
