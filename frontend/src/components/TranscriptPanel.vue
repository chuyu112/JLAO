<template>
  <section class="panel">
    <header class="panel-header">
      <div>
        <div class="panel-title">实时转写</div>
        <div class="transcript-meta">主播语言与真实弹幕</div>
      </div>
      <div class="transcript-counts">
        <n-tag size="small">{{ transcripts.length }} 条主播</n-tag>
        <n-tag size="small" type="info">{{ commentEvents.length }} 条真实弹幕</n-tag>
      </div>
    </header>

    <div class="panel-body transcript-split-grid">
      <div class="transcript-column">
        <div class="transcript-column-title">主播语言</div>
        <div v-if="partialTranscript" class="transcript-partial">
          正在识别：{{ partialTranscript }}
        </div>
        <div v-if="transcripts.length === 0" class="empty-state compact">
          接入直播音频后，这里会出现主播实时讲解内容。
        </div>
        <div v-else class="transcript-list">
          <article v-for="item in orderedTranscripts" :key="item.id" class="transcript-item">
            <div class="transcript-text">{{ item.text }}</div>
            <div class="transcript-meta">
              #{{ item.index }} · {{ formatTime(item.created_at) }}
              <template v-if="item.keywords.length"> · 关键词：{{ item.keywords.join('、') }}</template>
            </div>
          </article>
        </div>
      </div>

      <div class="transcript-column comment-column">
        <div class="transcript-column-title">真实弹幕累积</div>
        <div v-if="commentEvents.length === 0" class="empty-state compact">
          暂无真实弹幕，虚拟客户不会显示在这里。
        </div>
        <div v-else class="comment-list">
          <article v-for="item in orderedComments" :key="item.id" class="comment-item" :class="{ alert: item.priority >= 3 }">
            <div class="comment-line">
              <span>{{ item.customer_nickname }}</span>
              <small>{{ formatTime(item.created_at) }}</small>
            </div>
            <p>{{ item.content }}</p>
            <div class="transcript-meta">{{ item.event_type }} · {{ item.customer_level }}</div>
          </article>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { NTag } from 'naive-ui'
import type { TranscriptSegment, VirtualCustomerEvent } from '../types'

const props = defineProps<{
  transcripts: TranscriptSegment[]
  partialTranscript: string
  commentEvents: VirtualCustomerEvent[]
}>()

const orderedTranscripts = computed(() => [...props.transcripts].slice(-30).reverse())
const orderedComments = computed(() => props.commentEvents.slice(0, 80))

function formatTime(value: string) {
  return new Date(value).toLocaleTimeString('zh-CN', { hour12: false })
}
</script>

<style scoped>
.transcript-counts {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.transcript-split-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.05fr) minmax(0, 0.95fr);
  gap: 10px;
  overflow: hidden;
}

.transcript-column {
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: auto;
  padding-right: 2px;
}

.transcript-column-title {
  position: sticky;
  top: 0;
  z-index: 1;
  margin-bottom: 8px;
  padding: 0 0 7px;
  color: #d7e7ef;
  font-size: 13px;
  font-weight: 700;
  background: #0c141c;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.comment-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.comment-item {
  padding: 8px 10px;
  border-radius: 6px;
  background: #111a22;
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.comment-item.alert {
  border-color: rgba(255, 209, 102, 0.45);
  background: rgba(255, 209, 102, 0.08);
}

.comment-line {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.comment-line span {
  min-width: 0;
  color: #ecf6f2;
  font-size: 13px;
  font-weight: 700;
  overflow-wrap: anywhere;
}

.comment-line small {
  flex: 0 0 auto;
  color: #89a1aa;
  font-size: 11px;
}

.comment-item p {
  margin: 6px 0 0;
  color: #d4e2dc;
  font-size: 13px;
  line-height: 1.5;
  overflow-wrap: anywhere;
}

@media (max-width: 1100px) {
  .transcript-split-grid {
    grid-template-columns: 1fr;
  }
}
</style>
