<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { api, errorMessage } from '../api'
const router = useRouter()
const loading = ref(false)
const registering = ref(false)
const form = reactive({ username: '', password: '' })
const registration = reactive({ name: '', college: '', confirmation: '' })
async function login() {
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
        <h2>{{ registering ? '注册教师账号' : '登录' }}</h2>
        <el-form-item label="用户名"><el-input v-model.trim="form.username" maxlength="64" autocomplete="username" :placeholder="registering ? '至少 3 位，可用字母、数字、点、下划线和连字符' : ''" /></el-form-item>
        <template v-if="registering">
          <el-form-item label="姓名"><el-input v-model.trim="registration.name" maxlength="64" autocomplete="name" /></el-form-item>
          <el-form-item label="院系（选填）"><el-input v-model.trim="registration.college" maxlength="128" /></el-form-item>
        </template>
        <el-form-item label="密码"><el-input v-model="form.password" maxlength="128" type="password" show-password :autocomplete="registering ? 'new-password' : 'current-password'" :placeholder="registering ? '至少 12 位' : ''" /></el-form-item>
        <el-form-item v-if="registering" label="确认密码"><el-input v-model="registration.confirmation" maxlength="128" type="password" show-password autocomplete="new-password" /></el-form-item>
        <el-button type="primary" native-type="submit" :loading="loading" :disabled="!form.username || !form.password || (registering && (!registration.name || form.password.length < 12 || !registration.confirmation))">{{ registering ? '注册' : '登录' }}</el-button>
        <el-button link type="primary" :disabled="loading" @click="registering = !registering; form.password = ''; registration.confirmation = ''">{{ registering ? '已有账号，返回登录' : '注册教师账号' }}</el-button>
      </el-form>
    </div>
  </div>
</template>
