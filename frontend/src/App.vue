<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Document, House, Medal, Setting, User } from '@element-plus/icons-vue'
import { api, clearSession } from './api'

const route = useRoute()
const router = useRouter()
const isLogin = computed(() => route.path === '/login')
const passwordRequired = computed(() => route.path === '/account' && Boolean(localStorage.getItem('password_change_required')))
const account = ref<{ name: string; is_admin: boolean }>()
const menu = [
  ['/', '工作台', House], ['/achievements', '成果库', Medal], ['/titles', '职称申报', Document],
  ['/annual', '年度档案', Document], ['/profile', '个人档案', User],
] as const
const childPages: Record<string, { parent: string; title: string }> = {
  '/awards': { parent: '/achievements', title: '获奖成果' },
  '/files': { parent: '/achievements', title: '成果附件' },
  '/materials': { parent: '/titles', title: '申报材料' },
  '/analytics': { parent: '/annual', title: '成果分析' },
  '/ai': { parent: '/annual', title: 'AI 成果总结' },
}
const activePage = computed(() => childPages[route.path]?.parent || route.path)
const pageTitle = computed(() => childPages[route.path]?.title || menu.find(item => item[0] === route.path)?.[1]
  || (route.path === '/admin' ? '后台管理' : '账号安全'))

watch(isLogin, async login => {
  account.value = undefined
  if (login || !localStorage.getItem('token')) return
  try { account.value = (await api.get('/auth/me')).data } catch { /* Handled by the API client. */ }
}, { immediate: true })

function logout() {
  clearSession()
  router.push('/login')
}
</script>

<template>
  <router-view v-if="isLogin" />
  <main v-else-if="passwordRequired" class="password-gate">
    <div>
      <h2>修改临时密码</h2>
      <router-view />
      <el-button link type="primary" @click="logout">退出登录</el-button>
    </div>
  </main>
  <div v-else class="shell">
    <aside class="sidebar">
      <div class="brand"><div class="brand-mark">职</div><b>教师职称材料管理</b></div>
      <el-menu router :default-active="activePage">
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
        <h2>{{ pageTitle }}</h2>
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
      <section class="page">
        <nav v-if="activePage === '/achievements'" class="toolbar">
          <router-link to="/achievements">全部成果</router-link>
          <router-link to="/awards">获奖模板</router-link>
          <router-link to="/files">查找附件</router-link>
        </nav>
        <nav v-if="activePage === '/annual'" class="toolbar">
          <router-link to="/annual">年度档案</router-link>
          <router-link to="/analytics">成果分析</router-link>
          <router-link to="/ai">AI 成果总结</router-link>
        </nav>
        <router-view />
      </section>
    </main>
  </div>
</template>
<style scoped>
.password-gate { min-height: 100dvh; display: grid; place-items: center; padding: 24px; }
.password-gate > div { width: min(100%, 500px); }
.password-gate .el-button { margin-top: 12px; }
:global(body:has(.password-gate)) { min-width: 0; }
</style>
