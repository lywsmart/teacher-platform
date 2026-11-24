<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { api, clearSession, errorMessage } from '../api'
const router = useRouter()
const form = reactive({ current_password: '', new_password: '' })
const busy = ref(false)
const passwordRequired = Boolean(localStorage.getItem('password_change_required'))
async function save() {
  if (busy.value || !form.current_password || [...form.new_password].length < 6) return
  busy.value = true
  try {
    await api.put('/auth/password', form)
    clearSession()
    ElMessage.success('密码已修改，请重新登录')
    await router.push('/login')
  } catch (error) { ElMessage.error(errorMessage(error)) }
  finally { busy.value = false }
}
</script>
<template>
  <section class="panel" style="max-width:520px">
    <p v-if="passwordRequired">请输入当前临时密码并设置新密码，然后重新登录。</p>
    <el-form label-position="top" @submit.prevent="save">
      <el-form-item label="当前密码"><el-input v-model="form.current_password" type="password" autocomplete="current-password" /></el-form-item>
      <el-form-item label="新密码（至少 6 位）"><el-input v-model="form.new_password" maxlength="128" type="password" show-password autocomplete="new-password" /></el-form-item>
      <el-button type="primary" native-type="submit" :loading="busy" :disabled="!form.current_password || [...form.new_password].length < 6">修改密码</el-button>
    </el-form>
  </section>
</template>
