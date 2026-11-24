<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { DataAnalysis, Document, Files, House, Medal, Setting, User } from '@element-plus/icons-vue'
import { api } from './api'

const route = useRoute()
const router = useRouter()
const isLogin = computed(() => route.path === '/login')
const account = ref<{ name: string; is_admin: boolean }>()
const menu = [
  ['/', '工作台', House], ['/titles', '职称申报', Document], ['/materials', '申报材料', Files],
  ['/awards', '获奖成果', Medal], ['/achievements', '成果管理', Medal], ['/files', '成果附件', Files],
  ['/annual', '年度档案', Document], ['/analytics', '成果分析', DataAnalysis],
  ['/ai', 'AI 成果总结', Document], ['/profile', '个人档案', User],
] as const

watch(isLogin, async login => {
  account.value = undefined
  if (login || !localStorage.getItem('token')) return
  try { account.value = (await api.get('/auth/me')).data } catch { /* Handled by the API client. */ }
}, { immediate: true })

function logout() {
  localStorage.removeItem('token')
  router.push('/login')
}
</script>

<template>
  <router-view v-if="isLogin" />
  <div v-else class="shell">
    <aside class="sidebar">
      <div class="brand"><div class="brand-mark">职</div><b>教师职称材料管理</b></div>
      <el-menu router :default-active="route.path">
        <el-menu-item v-for="[path, label, icon] in menu" :key="path" :index="path">
          <el-icon><component :is="icon" /></el-icon><span>{{ label }}</span>
        </el-menu-item>
        <el-menu-item v-if="account?.is_admin" index="/admin">
          <el-icon><Setting /></el-icon><span>后台管理</span>
        </el-menu-item>
      </el-menu>
    </aside>
    <main class="main">
      <header>
        <h2>{{ menu.find(item => item[0] === route.path)?.[1] || (route.path === '/admin' ? '后台管理' : '账号安全') }}</h2>
        <el-dropdown>
          <div class="user-chip"><el-avatar :size="34">{{ account?.name?.[0] || '教' }}</el-avatar>{{ account?.name || '我的账号' }}</div>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item @click="router.push('/account')">修改密码</el-dropdown-item>
              <el-dropdown-item @click="logout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </header>
      <section class="page"><router-view /></section>
    </main>
  </div>
</template>
