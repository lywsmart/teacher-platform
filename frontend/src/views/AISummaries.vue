<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { api, errorMessage } from '../api'

type Summary = { id: number; summary_type: string; generated_content: string; edited_content?: string }
type Project = { id: number; name: string }
const route = useRoute()
const projectId = Number(route.query.project) || undefined
const year = new Date().getFullYear()
const form = reactive({
  summary_type: projectId ? 'title' : 'annual', start_year: year, end_year: year,
  category: '', instructions: '', title_application_id: projectId,
})
const projects = ref<Project[]>([])
const list = ref<Summary[]>([])
const result = ref<Summary>()
const loading = ref(false)

async function load() { list.value = (await api.get('/ai-summaries')).data }
async function generate() {
  loading.value = true
  try {
    const title = form.summary_type === 'title'
    const payload = {
      summary_type: form.summary_type, instructions: form.instructions,
      ...(title ? { title_application_id: form.title_application_id }
        : { start_year: form.start_year, end_year: form.end_year, category: form.category || undefined }),
    }
    result.value = (await api.post('/ai-summaries/generate', payload)).data
    await load()
    ElMessage.success('总结已保存')
  } catch (error) { ElMessage.error(errorMessage(error)) }
  finally { loading.value = false }
}
onMounted(async () => {
  try {
    const [available] = await Promise.all([api.get('/title-applications'), load()])
    projects.value = available.data
    if (!projects.value.some(project => project.id === form.title_application_id)) form.title_application_id = undefined
  } catch (error) { ElMessage.error(errorMessage(error)) }
})
</script>

<template>
  <div class="ai-layout">
    <section class="panel">
      <h3>生成成果总结</h3>
      <el-form label-position="top" @submit.prevent="generate">
        <el-form-item label="总结类型">
          <el-select v-model="form.summary_type">
            <el-option label="年度成果总结" value="annual" /><el-option label="职称业绩总结" value="title" /><el-option label="分类成果总结" value="category" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="form.summary_type === 'title'" label="申报项目">
          <el-select v-model="form.title_application_id" placeholder="只使用该项目的已选成果">
            <el-option v-for="project in projects" :key="project.id" :label="project.name" :value="project.id" />
          </el-select>
        </el-form-item>
        <template v-else>
          <div class="grid-2">
            <el-form-item label="开始年度"><el-input-number v-model="form.start_year" /></el-form-item>
            <el-form-item label="结束年度"><el-input-number v-model="form.end_year" /></el-form-item>
          </div>
          <el-form-item label="指定类别"><el-input v-model="form.category" /></el-form-item>
        </template>
        <el-form-item label="写作要求"><el-input v-model="form.instructions" type="textarea" /></el-form-item>
        <el-button type="primary" native-type="submit" :loading="loading" :disabled="form.summary_type === 'title' && !form.title_application_id">生成并保存</el-button>
      </el-form>
    </section>
    <section class="panel">
      <h3>生成结果</h3>
      <div v-if="result" class="summary-text">{{ result.edited_content || result.generated_content }}</div>
      <div v-else class="empty">选择范围后生成总结。</div>
    </section>
    <section class="panel history">
      <h3>历史记录</h3>
      <el-table :data="list" @row-click="(row: Summary) => result = row">
        <el-table-column prop="summary_type" label="类型" />
        <el-table-column prop="start_year" label="开始年度" />
        <el-table-column prop="end_year" label="结束年度" />
        <el-table-column prop="created_at" label="创建时间" />
      </el-table>
    </section>
  </div>
</template>
