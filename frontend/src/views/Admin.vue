<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api, errorMessage } from '../api'
import AdminEvidence from './AdminEvidence.vue'
import Settings from './Settings.vue'

type User = { id: number; username: string; name: string; college: string; is_active: boolean; is_admin: boolean }
const users = ref<User[]>([])
const next = ref<number | null>(null)
const form = reactive({ username: '', name: '', college: '', password: '' })
const creating = ref(false)

async function load(after = 0) {
  try {
    const { data } = await api.get('/admin/users', { params: { after } })
    users.value = after ? [...users.value, ...data.items] : data.items
    next.value = data.next
  } catch (error) { ElMessage.error(errorMessage(error)) }
}

async function create() {
  creating.value = true
  try {
    await api.post('/admin/users', form)
    Object.assign(form, { username: '', name: '', college: '', password: '' })
    await load()
    ElMessage.success('教师账号已开通')
  } catch (error) { ElMessage.error(errorMessage(error)) }
  finally { creating.value = false }
}

async function update(user: User, newPassword?: string) {
  try {
    const payload = newPassword ? { password: newPassword } : { is_active: !user.is_active }
    const { data } = await api.patch(`/admin/users/${user.id}`, payload)
    Object.assign(user, data)
    ElMessage.success('账号已更新')
  } catch (error) { ElMessage.error(errorMessage(error)) }
}

async function reset(user: User) {
  try {
    const result = await ElMessageBox.prompt('请输入至少 12 位的新密码', `重置 ${user.username} 的密码`, {
      inputType: 'password', inputPattern: /^.{12,128}$/, inputErrorMessage: '密码需为 12–128 位',
    })
    await update(user, result.value)
  } catch { /* User canceled. */ }
}
onMounted(() => load())
</script>

<template>
  <el-tabs>
    <el-tab-pane label="教师账号">
      <section class="panel">
        <h3>开通教师账号</h3>
        <el-form class="toolbar" @submit.prevent="create">
          <el-input v-model="form.username" aria-label="账号" placeholder="账号" autocomplete="off" style="width:155px" />
          <el-input v-model="form.name" aria-label="姓名" placeholder="姓名" style="width:140px" />
          <el-input v-model="form.college" aria-label="院系" placeholder="院系（可选）" style="width:160px" />
          <el-input v-model="form.password" aria-label="初始密码" type="password" placeholder="初始密码（至少 12 位）" autocomplete="new-password" style="width:210px" />
          <el-button native-type="submit" type="primary" :loading="creating" :disabled="!form.name.trim() || form.username.length < 3 || form.password.length < 12">开通账号</el-button>
        </el-form>
        <el-table :data="users">
          <el-table-column prop="username" label="账号" />
          <el-table-column prop="name" label="姓名" />
          <el-table-column prop="college" label="院系" />
          <el-table-column label="角色"><template #default="{ row }">{{ row.is_admin ? '管理员' : '教师' }}</template></el-table-column>
          <el-table-column label="状态"><template #default="{ row }"><el-tag :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? '正常' : '停用' }}</el-tag></template></el-table-column>
          <el-table-column label="操作" width="175">
            <template #default="{ row }">
              <template v-if="!row.is_admin">
                <el-button link type="primary" @click="reset(row)">重置密码</el-button>
                <el-button link :type="row.is_active ? 'danger' : 'primary'" @click="update(row)">{{ row.is_active ? '停用' : '启用' }}</el-button>
              </template>
            </template>
          </el-table-column>
        </el-table>
        <el-button v-if="next" style="margin-top: 12px" @click="load(next)">加载更多</el-button>
      </section>
    </el-tab-pane>
    <el-tab-pane label="佐证材料" lazy><AdminEvidence /></el-tab-pane>
    <el-tab-pane label="系统备份与设置" lazy><Settings /></el-tab-pane>
  </el-tabs>
</template>
