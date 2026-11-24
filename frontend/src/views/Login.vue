<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { api, errorMessage } from '../api'
const router = useRouter()
const loading = ref(false)
const registering = ref(false)
const form = reactive({ username: '', password: '' })
const registration = reactive({ name: '', college: '', confirmation: '' })
const canSubmit = computed(() => !loading.value && form.username && form.password &&
  (!registering.value || (form.username.length >= 3 && registration.name &&
    [...form.password].length >= 6 && registration.confirmation)))

async function login() {
  if (!canSubmit.value) return
  if (registering.value && form.password !== registration.confirmation) {
    ElMessage.warning('两次输入的密码不一致')
    return
  }
  loading.value = true
  try {
    if (registering.value) {
      await api.post('/auth/register', { ...form, name: registration.name.trim(), college: registration.college.trim() })
      registering.value = false
      form.password = ''
      registration.confirmation = ''
      ElMessage.success('教师账号已注册，请登录')
      return
    }
    const { data } = await api.post('/auth/login', form)
    localStorage.setItem('token', data.access_token)
    if (data.password_change_required) localStorage.setItem('password_change_required', '1')
    else localStorage.removeItem('password_change_required')
    await router.push(data.password_change_required ? '/account' : '/')
  } catch (error) { ElMessage.error(errorMessage(error)) }
  finally { loading.value = false }
}
</script>
<template>
  <main class="auth-screen">
    <div class="auth-background" aria-hidden="true">
      <div class="auth-stars"></div>
      <div class="auth-glow"></div>
      <div class="auth-grid"></div>
      <div class="auth-orbit auth-orbit-left"></div>
      <div class="auth-orbit auth-orbit-right"></div>
    </div>
    <section class="auth-card" aria-labelledby="auth-title">
      <div class="auth-brand">
        <span class="brand-mark" aria-hidden="true">职</span>
        <h1 id="auth-title">教师职称材料管理</h1>
      </div>
      <el-form label-position="top" @submit.prevent="login">
        <h2>{{ registering ? '注册教师账号' : '登录' }}</h2>
        <el-form-item label="用户名"><el-input v-model.trim="form.username" maxlength="64" autocomplete="username" :placeholder="registering ? '至少 3 位，可用字母、数字、点、下划线和连字符' : ''" /></el-form-item>
        <template v-if="registering">
          <el-form-item label="姓名"><el-input v-model.trim="registration.name" maxlength="64" autocomplete="name" /></el-form-item>
          <el-form-item label="院系（选填）"><el-input v-model.trim="registration.college" maxlength="128" /></el-form-item>
        </template>
        <el-form-item label="密码"><el-input v-model="form.password" maxlength="128" type="password" show-password :autocomplete="registering ? 'new-password' : 'current-password'" :placeholder="registering ? '至少 6 位' : ''" /></el-form-item>
        <el-form-item v-if="registering" label="确认密码"><el-input v-model="registration.confirmation" maxlength="128" type="password" show-password autocomplete="new-password" /></el-form-item>
        <el-button class="auth-submit" type="primary" native-type="submit" :loading="loading" :disabled="!canSubmit">{{ registering ? '注册' : '登录' }}</el-button>
        <el-button class="auth-switch" link type="primary" :disabled="loading" @click="registering = !registering; form.password = ''; registration.confirmation = ''">{{ registering ? '已有账号，返回登录' : '注册教师账号' }}</el-button>
      </el-form>
    </section>
  </main>
</template>

<style scoped>
:global(body:has(.auth-screen)) { min-width: 0; }
.auth-screen {
  min-height: 100vh;
  min-height: 100dvh;
  display: grid;
  place-items: center;
  padding: 32px 20px;
  position: relative;
  isolation: isolate;
  background: radial-gradient(ellipse at 52% 74%, #123d79 0%, #0b2045 38%, #071326 76%);
}
.auth-background { position: absolute; inset: 0; overflow: hidden; z-index: -1; pointer-events: none; }
.auth-stars {
  position: absolute;
  inset: 0;
  background-image: radial-gradient(circle, #73cffe 1px, transparent 1.8px), radial-gradient(circle, #6095ff 1px, transparent 2px);
  background-size: 87px 91px, 143px 113px;
  background-position: 12px 19px, 38px 71px;
  animation: auth-stars 9s ease-in-out infinite alternate;
  mask-image: linear-gradient(#000, transparent 86%);
}
.auth-glow {
  position: absolute;
  inset: -14% -12% 15%;
  background: radial-gradient(ellipse at 24% 38%, #2267e866 0%, transparent 37%),
              radial-gradient(ellipse at 76% 68%, #16befe40 0%, transparent 37%);
  animation: auth-glow 16s ease-in-out infinite alternate;
}
.auth-grid {
  position: absolute;
  width: 160%;
  height: 80%;
  left: -30%;
  bottom: -32%;
  background-image: linear-gradient(#489de450 1px, transparent 1px), linear-gradient(90deg, #489de450 1px, transparent 1px);
  background-size: 64px 64px;
  transform: perspective(400px) rotateX(55deg);
  mask-image: linear-gradient(transparent, #000 58%);
  animation: auth-grid 7s linear infinite;
}
.auth-orbit {
  position: absolute;
  width: min(53vw, 730px);
  aspect-ratio: 1;
  border-radius: 50%;
  border: 1px solid #70b9fe37;
  border-top-color: #50ddffbb;
  border-bottom-color: #417afb59;
  box-shadow: 0 0 30px #418dff23, inset 0 0 30px #418dff23;
  animation: auth-orbit 26s linear infinite;
}
.auth-orbit-left { top: 7%; left: -19vw; }
.auth-orbit-right { bottom: -15%; right: -17vw; animation-direction: reverse; }
.auth-card {
  width: min(100%, 438px);
  padding: clamp(24px, 5vw, 40px);
  border: 1px solid #e0ecff;
  border-radius: 20px;
  background: #f7fbff;
  box-shadow: 0 28px 90px #020d27b3, 0 0 42px #50a5ff24;
}
.auth-brand { display: flex; align-items: center; gap: 12px; color: #173b6b; }
.auth-brand .brand-mark { flex: 0 0 42px; }
.auth-brand h1 { margin: 0; font-size: clamp(16px, 4vw, 19px); font-weight: 700; }
.auth-card h2 { margin: 25px 0 18px; color: #0d2340; font-size: 25px; }
.auth-card :deep(.el-input__wrapper) { min-height: 40px; }
.auth-submit { width: 100%; min-height: 42px; }
.auth-switch.el-button { display: flex; margin: 17px auto 0; }
@keyframes auth-stars { from { opacity: .35; } to { opacity: .75; } }
@keyframes auth-glow { from { transform: translate(-4%, -4%); } to { transform: translate(5%, 6%); } }
@keyframes auth-grid { to { background-position: 0 64px; } }
@keyframes auth-orbit { to { transform: rotate(1turn); } }
@media (prefers-reduced-motion: reduce) {
  .auth-background > div { animation: none; }
}
</style>
