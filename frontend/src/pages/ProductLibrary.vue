<template>
  <main class="page">
    <app-top-nav title="翡翠商品库" subtitle="商品资料越完整，AI 建议越准确" />

    <section class="dashboard" style="height: auto">
      <div class="status-bar">
        <div>
          <div class="panel-title">Demo 商品样例</div>
          <div class="transcript-meta">第一版先用结构化商品资料驱动 AI 建议</div>
        </div>
        <n-button type="primary" secondary @click="store.initDemo">刷新商品</n-button>
      </div>

      <div class="main-grid" style="grid-template-columns: repeat(2, minmax(320px, 1fr))">
        <section v-for="product in store.products" :key="product.id" class="panel">
          <header class="panel-header">
            <div>
              <div class="panel-title">{{ product.name }}</div>
              <div class="transcript-meta">{{ product.category }} ｜ {{ product.water }} ｜ {{ product.color }}</div>
            </div>
            <n-tag type="success">{{ product.category }}</n-tag>
          </header>
          <div class="panel-body">
            <dl class="product-kv">
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
              <n-tag v-for="point in product.selling_points" :key="point" size="small" round>
                {{ point }}
              </n-tag>
            </div>
          </div>
        </section>
      </div>
    </section>
  </main>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { NButton, NTag } from 'naive-ui'
import AppTopNav from '../components/AppTopNav.vue'
import { useJlaoStore } from '../stores/jlao'

const store = useJlaoStore()

onMounted(() => {
  store.initDemo()
})
</script>
