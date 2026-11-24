<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api, download, errorMessage } from '../api'

type Application = { id: number; name: string }
type Material = { id: number; name: string; category: string; size: number }
const projects = ref<Application[]>([])
const selected = ref<number>()
const categories = ref<string[]>([])
const items = ref<Material[]>([])
const category = ref('')
const busy = ref(false)
const picker = ref<HTMLInputElement>()
const reviewTypes = ['教学为主型', '教学科研并重型', '社会服务型', '思政课教师', '专职辅导员']
const scoreGroups = [
  ['基本条件', 15], ['业务工作', 10], ['表彰奖励', 20],
  ['教学质量工程项目', 20], ['论文著作教材', 15], ['创新研究', 20],
] as const

async function load() {
  const id = selected.value
  items.value = []
  if (!id) return
  try {
    const { data } = await api.get(`/title-applications/${id}/materials`)
    if (id !== selected.value) return
    categories.value = data.categories
    items.value = data.items
  } catch (error) { ElMessage.error(errorMessage(error)) }
}

onMounted(async () => {
  try {
    projects.value = (await api.get('/title-applications')).data
    selected.value = projects.value[0]?.id
    await load()
  } catch (error) { ElMessage.error(errorMessage(error)) }
})

async function upload(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file || !selected.value || !category.value) return
  const body = new FormData()
  body.append('file', file)
  body.append('category', category.value)
  busy.value = true
  try {
    await api.post(`/title-applications/${selected.value}/materials`, body)
    await load()
    ElMessage.success('材料已上传')
  } catch (error) { ElMessage.error(errorMessage(error)) }
  finally { busy.value = false; input.value = '' }
}

async function save(item: Material) {
  try { await download(`/title-applications/${selected.value}/materials/${item.id}`, item.name) }
  catch (error) { ElMessage.error(errorMessage(error)) }
}
</script>

<template>
  <section class="panel">
    <h3>申报材料</h3>
    <p class="muted">按申报项目归档证明、加分明细和审核表。</p>
    <el-collapse style="margin-bottom: 20px">
      <el-collapse-item title="2026 年柳州城市职业学院材料整理参考" name="guide">
        <p>评审类型包括{{ reviewTypes.join('、') }}。准备材料时请对照申报职称和评审类型的具体条件。</p>
        <p>加分表分为以下六项。建议逐项写明成果名称、时间、级别、排名或参与方式，并上传相应证明和审核表。</p>
        <div class="toolbar">
          <el-tag v-for="[name, points] in scoreGroups" :key="name">{{ name }} {{ points }} 分</el-tag>
        </div>
        <p class="muted">参考附件 2《专业技术资格评审条件》及附件 18《职称评审加分计算表》。具体得分由审核部门核定。</p>
      </el-collapse-item>
    </el-collapse>
    <div v-if="projects.length" class="toolbar">
      <el-select v-model="selected" aria-label="申报项目" style="width:240px" @change="load">
        <el-option v-for="project in projects" :key="project.id" :label="project.name" :value="project.id" />
      </el-select>
      <el-select v-model="category" placeholder="选择材料类别" style="width:220px">
        <el-option v-for="name in categories" :key="name" :value="name" />
      </el-select>
      <el-button type="primary" :loading="busy" :disabled="!selected || !category" @click="picker?.click()">上传材料</el-button>
      <input ref="picker" hidden type="file" accept=".pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.jpg,.jpeg,.png,.zip" @change="upload" />
    </div>
    <el-table v-if="projects.length" :data="items" empty-text="该项目还没有上传材料">
      <el-table-column prop="name" label="文件名" min-width="200" />
      <el-table-column prop="category" label="材料类别" min-width="160" />
      <el-table-column prop="status" label="审核状态" width="110" />
      <el-table-column prop="note" label="审核意见" min-width="125" />
      <el-table-column label="大小" width="110"><template #default="{ row }">{{ (row.size / 1024).toFixed(1) }} KB</template></el-table-column>
      <el-table-column label="操作" width="90"><template #default="{ row }"><el-button link type="primary" @click="save(row)">下载</el-button></template></el-table-column>
    </el-table>
    <router-link v-else to="/titles">前往职称申报创建项目</router-link>
  </section>
</template>
