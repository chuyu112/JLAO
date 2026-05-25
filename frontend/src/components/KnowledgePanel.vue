<template>
  <section class="panel knowledge-panel">
    <div class="panel-header">
      <div>
        <h2>知识库命中</h2>
        <p>{{ sourceLabel }}</p>
      </div>
      <span class="count-pill">{{ hits.length }}</span>
    </div>

    <div v-if="hits.length" class="knowledge-list">
      <article v-for="chunk in hits" :key="chunk.id" class="knowledge-item">
        <div class="item-title">
          <span>{{ chunk.heading }}</span>
          <small>{{ chunk.tags.join(' / ') || '知识片段' }}</small>
        </div>
        <p>{{ trimContent(chunk.content) }}</p>
      </article>
    </div>
    <div v-else class="empty-state compact">等待转写触发知识库检索。</div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { WikiChunk } from '../types'

const props = defineProps<{
  hits: WikiChunk[]
  total: number
}>()

const sourceLabel = computed(() => (props.total ? `已索引 ${props.total} 个片段` : '未索引知识库'))

function trimContent(content: string) {
  return content.length > 92 ? `${content.slice(0, 92)}...` : content
}
</script>

<style scoped>
.knowledge-panel {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.panel-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}
.panel-header h2 {
  margin: 0;
  font-size: 15px;
}
.panel-header p {
  margin: 4px 0 0;
  font-size: 12px;
  color: #8fa3b6;
}
.count-pill {
  min-width: 26px;
  height: 22px;
  border-radius: 11px;
  background: rgba(34, 211, 166, 0.16);
  color: #6ff0cf;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
}
.knowledge-list {
  display: grid;
  gap: 8px;
}
.knowledge-item {
  padding: 10px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
}
.item-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
}
.item-title small {
  color: #8fa3b6;
  font-size: 11px;
  white-space: nowrap;
}
.knowledge-item p {
  margin: 6px 0 0;
  color: #c6d3df;
  line-height: 1.5;
  font-size: 12px;
}
</style>
