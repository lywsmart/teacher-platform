<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api, errorMessage } from '../api'

type Status = { configured: boolean; source: 'admin' | 'environment' | null }
const status = ref<Status>()
const key = ref('')
const busy = ref(false)
const unsecured = location.protocol === 'http:' && !['localhost', '127.0.0.1', '[::1]'].includes(location.hostname)
const statusText = computed(() => {
  if (!status.value) return '暂时无法读取配置状态'
  if (status.value.source === 'admin') return '已配置 · 后台密钥'
  if (status.value.source === 'environment') return '已配置 · 服务器环境变量'
  return '尚未配置'
})

async function refresh() {
  busy.value = true
  try { status.value = (await api.get('/admin/ai-config')).data }
  catch (error) { ElMessage.error(errorMessage(error)) }
  finally { busy.value = false }
}

async function save() {
  if (busy.value || !key.value.trim()) return
  busy.value = true
  try {
    status.value = (await api.put('/admin/ai-config', { api_key: key.value.trim() })).data
    key.value = ''
    ElMessage.success('DeepSeek 密钥已保存，即时生效')
  } catch (error) { ElMessage.error(errorMessage(error)) }
  finally { busy.value = false }
}

async function remove() {
  try {
    await ElMessageBox.confirm('清除后，系统将使用服务器环境变量中的密钥（如已配置）。', '清除后台密钥', { type: 'warning' })
  } catch { return }
  busy.value = true
  try {
    status.value = (await api.delete('/admin/ai-config')).data
    key.value = ''
    ElMessage.success('后台密钥已清除')
  } catch (error) { ElMessage.error(errorMessage(error)) }
  finally { busy.value = false }
}

onMounted(refresh)
</script>

<template>
  <section class="panel ai-config" v-loading="busy">
    <div class="panel-title">
      <h3>DeepSeek API Key</h3>
      <el-tag :type="status?.configured ? 'success' : 'info'">{{ statusText }}</el-tag>
    </div>
    <p class="muted">此密钥用于全站 AI 成果总结。保存后页面只显示配置状态。</p>
    <el-alert v-if="unsecured" title="当前连接使用 HTTP，请通过 HTTPS 访问后台后再填写密钥。" type="warning" :closable="false" show-icon />
    <el-form label-position="top" @submit.prevent="save">
      <el-form-item :label="status?.configured ? '替换密钥' : '输入密钥'">
        <el-input v-model="key" type="password" autocomplete="off" maxlength="1024" placeholder="输入 DeepSeek API Key" />
      </el-form-item>
      <el-button type="primary" native-type="submit" :disabled="busy || !key.trim()">保存密钥</el-button>
      <el-button v-if="status?.source === 'admin'" link type="danger" :disabled="busy" @click="remove">清除后台密钥</el-button>
    </el-form>
  </section>
</template>

<style scoped>
.ai-config { max-width: 640px; }
.ai-config .el-form { margin-top: 20px; }
</style>
