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
const navigationGroups: Record<string, { label: string; links: [string, string][] }> = {
  '/achievements': {
    label: '成果库导航',
    links: [['/achievements', '全部成果'], ['/awards', '获奖模板'], ['/files', '查找附件']],
  },
  '/annual': {
    label: '年度档案导航',
    links: [['/annual', '年度档案'], ['/analytics', '成果分析'], ['/ai', 'AI 成果总结']],
  },
}
const sectionNavigation = computed(() => navigationGroups[activePage.value])
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
          <button class="user-chip" type="button">
            <el-avatar :size="30" aria-hidden="true">{{ account?.name?.[0] || '教' }}</el-avatar>
            {{ account?.name || '我的账号' }}
          </button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item @click="router.push('/account')">修改密码</el-dropdown-item>
              <el-dropdown-item @click="logout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </header>
      <section class="page">
        <nav v-if="sectionNavigation" :aria-label="sectionNavigation.label" class="section-nav">
          <router-link v-for="[path, label] in sectionNavigation.links" :key="path" :to="path">
            {{ label }}
          </router-link>
        </nav>
        <router-view />
      </section>
    </main>
  </div>
</template>
<style scoped>
.user-chip {
  min-height: 40px;
  padding: 4px 10px 4px 5px;
  border: 1px solid var(--action-secondary-border);
  border-radius: 10px;
  background: #fff;
  color: var(--action-secondary-ink);
  font-weight: 600;
}
.user-chip:hover { background: var(--action-subtle); }

.section-nav {
  display: inline-flex;
  flex-wrap: wrap;
  gap: 4px;
  max-width: 100%;
  margin-bottom: 20px;
  padding: 4px;
  border: 1px solid #d6e4f7;
  border-radius: 12px;
  background: #e5eefb;
}
.section-nav a {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 40px;
  padding: 0 14px;
  border: 1px solid transparent;
  border-radius: 8px;
  color: #395577;
  font-size: 14px;
  font-weight: 500;
  text-decoration: none;
}
.section-nav a:hover { color: #134790; background: #edf5ff; }
.section-nav a[aria-current="page"] {
  color: #124c9f;
  font-weight: 650;
  background: #f7fbff;
  border-color: #cbdcf3;
  box-shadow: 0 1px 2px #10284c10;
}
.section-nav a:focus-visible { outline: 2px solid #175cce; outline-offset: -2px; }

.password-gate { min-height: 100dvh; display: grid; place-items: center; padding: 24px; }
.password-gate > div { width: min(100%, 500px); }
.password-gate .el-button { margin-top: 12px; }
:global(body:has(.password-gate)) { min-width: 0; }
</style>
