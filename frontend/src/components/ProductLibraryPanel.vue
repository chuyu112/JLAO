<template>
  <section class="panel product-library-panel">
    <header class="panel-header">
      <div>
        <div class="panel-title">商品库</div>
        <div class="transcript-meta">{{ products.length }} 件直播在售商品 · 当前识别 {{ detectedName || '待识别' }}</div>
      </div>
      <n-tag size="small" type="success">直播在售</n-tag>
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
          <span class="status-badge">直播在售</span>
        </div>
        <p>{{ product.color || '颜色待识别' }} · {{ product.water || '种水待识别' }} · {{ product.style || product.category }}</p>
        <small>
          {{ product.theme ? `题材：${product.theme}` : product.size || '尺寸待补充' }}
          · 证据 {{ product.evidence_image_paths.length + product.evidence_texts.length }} 条
        </small>
        <div class="product-library-actions" @click.stop>
          <n-button size="tiny" secondary type="info" @click="openAnnotation(product)">
            人工标注
          </n-button>
        </div>
      </article>

      <div v-if="!visibleProducts.length" class="empty-state compact">
        暂无直播在售商品
      </div>
    </div>

    <n-modal v-model:show="annotationOpen" preset="card" title="人工标注翡翠属性" class="annotation-modal">
      <div v-if="annotationProduct" class="annotation-form">
        <div class="annotation-product-name">{{ annotationProduct.name }}</div>
        <n-select
          v-model:value="annotationDraft.color"
          filterable
          tag
          clearable
          :options="jadeSelectOptions.colors"
          placeholder="颜色：阳绿 / 蓝水 / 白冰 / 紫罗兰..."
        />
        <n-select
          v-model:value="annotationDraft.water"
          filterable
          tag
          clearable
          :options="jadeSelectOptions.waters"
          placeholder="种水：玻璃种 / 高冰 / 冰种 / 糯冰..."
        />
        <n-select
          v-model:value="annotationDraft.style"
          filterable
          tag
          clearable
          :options="jadeSelectOptions.styles"
          placeholder="样式：手镯 / 珠串 / 蛋面 / 吊坠..."
        />
        <n-select
          v-model:value="annotationDraft.theme"
          filterable
          tag
          clearable
          :options="jadeSelectOptions.themes"
          placeholder="题材：观音 / 佛公 / 如意 / 山水..."
        />
        <div class="annotation-hint">
          可只填需要校正的字段；保存后会更新商品库，并进入反馈学习样本池。
        </div>
        <div class="annotation-actions">
          <n-button secondary @click="annotationOpen = false">取消</n-button>
          <n-button type="primary" :loading="annotationSaving" @click="saveAnnotation">保存标注</n-button>
        </div>
        <div v-if="annotationError" class="annotation-error">{{ annotationError }}</div>
      </div>
    </n-modal>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { NButton, NModal, NSelect, NTag } from 'naive-ui'
import { annotateProductJade, fetchJadeTaxonomyOptions } from '../api/jlao'
import type { JadeTaxonomyOptions, Product } from '../types'

const props = defineProps<{
  products: Product[]
  currentProductId: string | null
  detectedName?: string
}>()

const visibleProducts = computed(() => props.products.slice(0, 8))
const emit = defineEmits<{
  'select-product': [id: string]
  'product-annotated': [product: Product]
}>()
const annotationOpen = ref(false)
const annotationSaving = ref(false)
const annotationError = ref('')
const annotationProduct = ref<Product | null>(null)
const jadeTaxonomy = ref<JadeTaxonomyOptions | null>(null)
const annotationDraft = reactive({
  color: '',
  water: '',
  style: '',
  theme: '',
})
const fallbackTaxonomy = {
  colors: ['帝王绿', '阳绿', '辣绿', '苹果绿', '豆绿', '绿色', '蓝水', '晴水', '油青', '紫罗兰', '春带彩', '白冰', '无色', '白底青', '飘花', '黄翡', '冰黄', '洒金', '墨翠', '红翡', '多彩'],
  waters: ['玻璃种', '高冰', '冰种', '冰胶', '起冰', '冰糯', '糯冰', '起胶', '糯化', '细糯', '糯种', '豆种'],
  styles: ['手镯', '珠串', '蛋面', '戒面', '戒指', '挂件', '吊坠', '平安扣', '摆件', '把件', '耳饰'],
  themes: ['观音', '佛公', '如意', '叶子', '山水', '貔貅', '葫芦', '无事牌', '财神', '龙', '福瓜', '福豆'],
}
const jadeSelectOptions = computed(() => ({
  colors: toOptions(jadeTaxonomy.value?.colors || fallbackTaxonomy.colors),
  waters: toOptions(jadeTaxonomy.value?.waters || fallbackTaxonomy.waters),
  styles: toOptions(jadeTaxonomy.value?.styles || fallbackTaxonomy.styles),
  themes: toOptions(jadeTaxonomy.value?.themes || fallbackTaxonomy.themes),
}))

onMounted(async () => {
  try {
    jadeTaxonomy.value = await fetchJadeTaxonomyOptions()
  } catch {
    jadeTaxonomy.value = null
  }
})

function toOptions(items: string[]) {
  return items.map((item) => ({ label: item, value: item }))
}

function openAnnotation(product: Product) {
  annotationProduct.value = product
  annotationDraft.color = product.color || ''
  annotationDraft.water = product.water || ''
  annotationDraft.style = product.style || ''
  annotationDraft.theme = product.theme || ''
  annotationError.value = ''
  annotationOpen.value = true
}

async function saveAnnotation() {
  if (!annotationProduct.value) return
  annotationSaving.value = true
  annotationError.value = ''
  try {
    await annotateProductJade(annotationProduct.value.id, {
      color: annotationDraft.color,
      water: annotationDraft.water,
      style: annotationDraft.style,
      theme: annotationDraft.theme,
    })
    emit('product-annotated', {
      ...annotationProduct.value,
      color: annotationDraft.color,
      water: annotationDraft.water,
      style: annotationDraft.style,
      theme: annotationDraft.theme,
    })
    annotationOpen.value = false
  } catch (error) {
    annotationError.value = error instanceof Error ? error.message : '标注保存失败'
  } finally {
    annotationSaving.value = false
  }
}
</script>

<style scoped>
.product-library-panel {
  min-height: 0;
}

.product-library-body {
  display: grid;
  gap: 8px;
  padding: 8px;
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

.status-badge {
  padding: 2px 8px;
  border-radius: 4px;
  color: #22d3a6;
  font-size: 11px;
  white-space: nowrap;
  background: rgba(34, 211, 166, 0.2);
}

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

.product-library-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 7px;
}

.annotation-form {
  display: grid;
  gap: 10px;
}

.annotation-product-name {
  color: #17351f;
  font-weight: 700;
}

.annotation-hint,
.annotation-error {
  font-size: 12px;
  line-height: 1.5;
}

.annotation-hint {
  color: rgba(15, 23, 42, 0.58);
}

.annotation-error {
  color: #b91c1c;
}

.annotation-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

:global(.annotation-modal) {
  max-width: 420px;
}
</style>
