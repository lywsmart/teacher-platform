<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { api, errorMessage } from '../api'
const router = useRouter()
const loading = ref(false)
const form = reactive({ username: '', password: '' })
async function login() {
  loading.value = true
  try {
    const { data } = await api.post('/auth/login', form)
    localStorage.setItem('token', data.access_token)
    await router.push('/')
  } catch (error) { ElMessage.error(errorMessage(error)) }
  finally { loading.value = false }
}
</script>
<template>
  <div class="login">
    <div class="login-art">
      <div class="brand"><div class="brand-mark">职</div><b>教师职称材料管理</b></div>
      <h1>教师职称申报工作台</h1>
    </div>
    <div class="login-card">
      <el-form class="login-box" label-position="top" @submit.prevent="login">
        <h2>登录</h2>
        <p class="muted">教师账号由系统管理员开通。</p>
        <el-form-item label="账号"><el-input v-model.trim="form.username" autocomplete="username" /></el-form-item>
        <el-form-item label="密码"><el-input v-model="form.password" type="password" show-password autocomplete="current-password" /></el-form-item>
        <el-button type="primary" native-type="submit" :loading="loading" :disabled="!form.username || !form.password">登录</el-button>
      </el-form>
    </div>
  </div>
</template>
