<template>
  <n-config-provider :theme="darkTheme" :theme-overrides="themeOverrides">
    <n-message-provider>
      <router-view />
    </n-message-provider>
  </n-config-provider>
</template>

<script setup lang="ts">
import { darkTheme, NConfigProvider, NMessageProvider } from 'naive-ui'

const themeOverrides = {
  common: {
    primaryColor: '#22d3a6',
    primaryColorHover: '#5ee8c7',
    primaryColorPressed: '#12a97f',
    borderRadius: '6px',
    fontFamily: 'Inter, "Microsoft YaHei", "PingFang SC", sans-serif',
    bodyColor: '#080d12',
    cardColor: '#121a22',
    modalColor: '#121a22',
    popoverColor: '#121a22',
    textColorBase: '#ecf7f4',
  },
}
</script>
