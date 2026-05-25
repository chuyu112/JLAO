<template>
  <section class="panel virtual-customer-panel">
    <div class="panel-header">
      <div>
        <h2>模拟客户线索</h2>
        <p>公开视频号观察样本 · 不沉淀真实客户</p>
      </div>
      <span class="count-pill">{{ customers.length }}</span>
    </div>

    <div class="customer-row">
      <article v-for="customer in topCustomers" :key="customer.id" class="customer-card">
        <div class="customer-name">
          <span>{{ customer.nickname }}</span>
          <b :class="{ vip: isHighValue(customer.level) }">{{ customer.level }}</b>
        </div>
        <p>{{ customer.preferred_colors.concat(customer.preferred_categories).join(' / ') }}</p>
        <small>{{ customer.budget_range }} · 已购 {{ formatAmount(customer.purchased_amount) }}</small>
      </article>
    </div>

    <div class="event-list">
      <article v-for="event in events.slice(0, 5)" :key="event.id" class="event-item" :class="{ alert: event.event_type === '高价值进房' }">
        <div>
          <span>{{ event.event_type }}</span>
          <small>{{ event.customer_nickname }} · {{ event.customer_level }}</small>
        </div>
        <p>{{ event.content }}</p>
      </article>
      <div v-if="!events.length" class="empty-state compact">等待转写中出现可训练的客户问题线索。</div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { VirtualCustomer, VirtualCustomerEvent } from '../types'

const props = defineProps<{
  customers: VirtualCustomer[]
  events: VirtualCustomerEvent[]
}>()

const topCustomers = computed(() => props.customers.slice(0, 4))

function isHighValue(level: string) {
  return ['高价值', 'VIP', '老客'].some((word) => level.includes(word))
}

function formatAmount(value: number) {
  return value ? `¥${Math.round(value).toLocaleString()}` : '暂无'
}
</script>

<style scoped>
.virtual-customer-panel {
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
  background: rgba(91, 141, 239, 0.18);
  color: #a9c2ff;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
}
.customer-row {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}
.customer-card,
.event-item {
  padding: 10px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
}
.customer-name,
.event-item > div {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}
.customer-name span,
.event-item span {
  font-size: 13px;
  font-weight: 600;
}
.customer-name b {
  font-size: 11px;
  color: #9fb0c1;
  font-weight: 600;
}
.customer-name b.vip {
  color: #ffd166;
}
.customer-card p,
.event-item p {
  margin: 6px 0 0;
  color: #c6d3df;
  font-size: 12px;
  line-height: 1.45;
}
.customer-card small,
.event-item small {
  color: #8fa3b6;
  font-size: 11px;
}
.event-list {
  display: grid;
  gap: 8px;
}
.event-item.alert {
  border-color: rgba(255, 209, 102, 0.45);
  background: rgba(255, 209, 102, 0.08);
}
</style>
