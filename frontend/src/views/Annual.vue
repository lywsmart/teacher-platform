<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api, download } from '../api'
const year = ref(new Date().getFullYear())
const data = ref<any>({ by_type: {}, items: [] })
async function load() { data.value = (await api.get(`/annual/${year.value}`)).data }
onMounted(load)
</script>
<template><div class="toolbar"><el-input-number v-model="year" @change="load"/><div class="spacer"/><el-button @click="download(`/annual/${year}/word`,`${year}年度成果汇总.docx`)">导出 Word</el-button></div><div class="metrics"><div v-for="x in [['成果总数',data.total],['证明材料',data.file_count],['年度积分',data.score],['教学成果',data.by_type['教学成果']],['科研成果',data.by_type['科研成果']]]" :key="x[0]" class="metric"><label>{{x[0]}}</label><strong>{{x[1]||0}}</strong></div></div><div class="panel"><h3>{{year}} 年完整成果档案</h3><el-table :data="data.items"><el-table-column prop="title" label="成果名称"/><el-table-column prop="achievement_type" label="类型"/><el-table-column prop="level" label="级别"/><el-table-column prop="score" label="积分"/></el-table></div></template>
