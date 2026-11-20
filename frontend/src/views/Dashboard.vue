<script setup lang="ts">
import { nextTick, onMounted, ref } from 'vue'
import * as echarts from 'echarts'
import { api } from '../api'
const data = ref<any>({ metrics: {}, trend: [], by_type: [], recent: [] })
const trend = ref<HTMLElement>()
const pie = ref<HTMLElement>()
onMounted(async () => {
  data.value = (await api.get('/dashboard')).data
  await nextTick()
  echarts.init(trend.value!).setOption({ tooltip:{trigger:'axis'}, xAxis:{type:'category',data:data.value.trend.map((x:any)=>x.year)}, yAxis:{type:'value'}, series:[{type:'line',smooth:true,data:data.value.trend.map((x:any)=>x.count),lineStyle:{color:'#26775b',width:3},areaStyle:{color:'rgba(38,119,91,.12)'}}] })
  echarts.init(pie.value!).setOption({ tooltip:{trigger:'item'}, legend:{bottom:0}, series:[{type:'pie',radius:['45%','68%'],data:data.value.by_type}] })
})
</script>
<template><div class="hero"><h2>今天，也为职业成长添上一笔。</h2><p>所有成果均来自您的真实档案，可随时检索、分析并用于职称材料。</p></div><div class="metrics"><div v-for="x in [['今年成果',data.metrics.this_year],['近三年成果',data.metrics.three_years],['近五年成果',data.metrics.five_years],['全部成果',data.metrics.total],['电子材料',data.metrics.files]]" :key="x[0]" class="metric"><label>{{x[0]}}</label><strong>{{x[1]||0}}</strong><em>真实档案统计</em></div></div><div class="grid-2"><div class="panel"><h3>历年成果趋势</h3><div ref="trend" class="charts"/></div><div class="panel"><h3>成果结构</h3><div ref="pie" class="charts"/></div></div><div class="panel" style="margin-top:18px"><div class="panel-title"><h3>最近新增成果</h3><router-link to="/achievements"><el-button type="primary">新增成果</el-button></router-link></div><el-table :data="data.recent"><el-table-column prop="title" label="成果名称"/><el-table-column prop="achievement_type" label="类型"/><el-table-column prop="year" label="年度"/></el-table></div></template>
