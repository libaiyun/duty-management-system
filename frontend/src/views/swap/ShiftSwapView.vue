<template>
  <section>
    <div class="header"><h1>换班申请</h1><el-button type="primary" @click="dialog = true">发起换班</el-button></div>
    <el-tabs v-model="tab" @tab-change="load">
      <el-tab-pane label="我发起的" name="initiated" />
      <el-tab-pane label="待我确认" name="pending" />
      <el-tab-pane label="与我相关" name="related" />
    </el-tabs>
    <el-table v-loading="loading" :data="items" border>
      <el-table-column prop="biz_no" label="单号" min-width="180" /><el-table-column label="类型" width="110"><template #default="{ row }">{{ row.swap_type === 'mutual' ? '互换' : '单向替班' }}</template></el-table-column>
      <el-table-column prop="applicant_name" label="申请人" width="110" /><el-table-column prop="source_duty_date" label="原班日期" width="120" /><el-table-column prop="target_person_name" label="目标人员" width="110" />
      <el-table-column label="状态" width="140"><template #default="{ row }"><el-tag :type="statusType(row.status)">{{ label(row.status) }}</el-tag></template></el-table-column>
      <el-table-column label="操作" width="180"><template #default="{ row }"><el-button v-if="tab === 'pending' && row.status === 'wait_target_confirm'" link type="primary" @click="confirm(row, true)">同意</el-button><el-button v-if="tab === 'pending' && row.status === 'wait_target_confirm'" link type="danger" @click="confirm(row, false)">拒绝</el-button><el-button v-if="tab === 'initiated' && ['draft','wait_target_confirm','wait_director_approval'].includes(row.status)" link @click="withdraw(row)">撤回</el-button><el-button v-if="tab === 'initiated' && ['approved','effective'].includes(row.status)" link type="danger" @click="cancel(row)">作废</el-button></template></el-table-column>
    </el-table>
    <el-dialog v-model="dialog" title="发起换班" width="680px"><el-alert v-if="!eligiblePersons.length" title="当前机房没有其他已绑定启用账号的值机员，暂不能发起换班。请先在账号角色页为目标人员绑定并启用账号。" type="warning" :closable="false" class="target-alert" /><el-form label-width="100px"><el-form-item label="换班类型"><el-radio-group v-model="form.swap_type"><el-radio value="mutual">互换班次</el-radio><el-radio value="single_cover">单向替班</el-radio></el-radio-group></el-form-item><el-form-item label="本人原班次"><el-select v-model="form.source_shift_id" placeholder="选择本人已发布班次"><el-option v-for="shift in sourceShifts" :key="shift.id" :label="shiftLabel(shift)" :value="shift.id" /></el-select></el-form-item><el-form-item label="目标人员"><el-select v-model="form.target_person_id" placeholder="选择目标人员" @change="loadTargetShifts"><el-option v-for="person in persons" :key="person.id" :label="personLabel(person)" :value="person.id" :disabled="!person.eligible" /></el-select></el-form-item><el-form-item v-if="form.swap_type === 'mutual'" label="对方班次"><div class="calendar-hint">选择目标人员后，直接点击日历中的班次。</div><el-calendar v-model="targetCalendarDate" class="swap-calendar"><template #date-cell="{ data }"><div class="calendar-cell"><span>{{ Number(data.day.slice(-2)) }}</span><el-button v-for="shift in targetShiftForDay(data.day)" :key="shift.id" size="small" :type="form.target_shift_id === shift.id ? 'primary' : 'default'" @click.stop="selectTargetShift(shift)">{{ shift.shift_name }}</el-button></div></template></el-calendar><el-select v-model="form.target_shift_id" placeholder="或从列表选择" class="fallback-select"><el-option v-for="shift in targetShifts" :key="shift.id" :label="shiftLabel(shift)" :value="shift.id" /></el-select></el-form-item><el-form-item label="原因"><el-input v-model="form.reason" type="textarea" /></el-form-item></el-form><template #footer><el-button @click="dialog=false">取消</el-button><el-button type="primary" :disabled="!eligiblePersons.length" @click="submit">提交</el-button></template></el-dialog>
  </section>
</template>
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { httpClient, resolveErrorMessage } from '@/services/http'
import { useAuthStore } from '@/stores/auth'
interface Swap { id:number; biz_no:string; swap_type:string; applicant_name:string; source_duty_date:string; target_person_name:string; status:string }
interface Option { id:number; name?:string; duty_date?:string; shift_name?:string; start_at?:string; eligible?:boolean; disabled_reason?:string|null }
const route=useRoute(); const tab=ref('initiated'); const loading=ref(false); const dialog=ref(Boolean(route.query.source_shift_id)); const items=ref<Swap[]>([])
const authStore=useAuthStore(); const persons=ref<Option[]>([]); const sourceShifts=ref<Option[]>([]); const targetShifts=ref<Option[]>([]); const targetCalendarDate=ref(new Date())
const eligiblePersons=ref<Option[]>([])
const form=ref({swap_type:'mutual',source_shift_id:Number(route.query.source_shift_id)||undefined,target_person_id:undefined as number|undefined,target_shift_id:undefined as number|undefined,reason:''})
async function load(){loading.value=true;try{items.value=(await httpClient.get<{items:Swap[]}>(`/shift-swaps?view=${tab.value}&page_size=100`)).data.items}catch(e){ElMessage.error(resolveErrorMessage(e,'加载换班记录失败'))}finally{loading.value=false}}
async function loadOptions(){try{persons.value=(await httpClient.get<Option[]>('/shift-swaps/eligible-persons')).data;eligiblePersons.value=persons.value.filter((person)=>person.eligible); if(authStore.personId) sourceShifts.value=(await httpClient.get<Option[]>(`/shift-swaps/eligible-shifts?person_id=${authStore.personId}`)).data}catch(e){ElMessage.error(resolveErrorMessage(e,'加载换班选项失败'))}}
async function loadTargetShifts(){form.value.target_shift_id=undefined;if(form.value.target_person_id) {targetShifts.value=(await httpClient.get<Option[]>(`/shift-swaps/eligible-shifts?person_id=${form.value.target_person_id}`)).data;const first=targetShifts.value[0]?.duty_date;if(first) targetCalendarDate.value=new Date(`${first}T00:00:00`)}}
function targetShiftForDay(day:string):Option[]{return targetShifts.value.filter((shift)=>shift.duty_date===day)}
function selectTargetShift(shift:Option):void{form.value.target_shift_id=shift.id}
function shiftLabel(shift:Option):string{return `${shift.duty_date || ''} ${shift.shift_name || ''}`.trim()}
function personLabel(person:Option):string{return person.eligible?person.name || '':`${person.name || ''}（${person.disabled_reason || '不可用'}）`}
async function submit(){try{await httpClient.post('/shift-swaps',form.value);ElMessage.success('换班申请已提交');dialog.value=false;await load()}catch(e){ElMessage.error(resolveErrorMessage(e,'提交失败'))}}
async function confirm(row:Swap, yes:boolean){let opinion:string|undefined;if(!yes){const r=await ElMessageBox.prompt('请填写拒绝原因','拒绝换班',{inputValidator:(v)=>!!v||'拒绝原因必填'});opinion=r.value}try{await httpClient.post(`/shift-swaps/${row.id}/${yes?'target-confirm':'target-reject'}`,{opinion});ElMessage.success('操作成功');await load()}catch(e){ElMessage.error(resolveErrorMessage(e,'操作失败'))}}
async function withdraw(row:Swap){try{await httpClient.post(`/shift-swaps/${row.id}/withdraw`);ElMessage.success('已撤回');await load()}catch(e){ElMessage.error(resolveErrorMessage(e,'撤回失败'))}}
async function cancel(row:Swap){try{await ElMessageBox.confirm('作废后将恢复原实际值班人员，是否继续？','作废换班',{type:'warning'});await httpClient.post(`/shift-swaps/${row.id}/cancel`);ElMessage.success('已作废');await load()}catch(e){if(e !== 'cancel') ElMessage.error(resolveErrorMessage(e,'作废失败'))}}
function label(s:string){return ({draft:'草稿',wait_target_confirm:'待对方确认',wait_director_approval:'待主任审批',approved:'已通过',effective:'已生效',rejected:'已拒绝',withdrawn:'已撤回',cancelled:'已作废'} as Record<string,string>)[s]||s}
function statusType(s:string):'success'|'danger'|'warning'|'info'{return s==='effective'||s==='approved'?'success':s==='rejected'?'danger':['withdrawn','cancelled','draft'].includes(s)?'info':'warning'} onMounted(async()=>{await load();await loadOptions()})
</script>
<style scoped>
.header{display:flex;justify-content:space-between;align-items:center;margin-bottom:12px}.header h1{margin:0}
.calendar-hint{color:var(--el-text-color-secondary);font-size:13px;margin-bottom:6px}
.target-alert{margin-bottom:16px}
.swap-calendar{width:100%;border:1px solid var(--el-border-color-lighter);border-radius:6px}.swap-calendar :deep(.el-calendar__header){padding:8px 12px}.swap-calendar :deep(.el-calendar-day){height:66px;padding:4px}.calendar-cell{display:grid;gap:2px}.calendar-cell span{font-size:12px}.calendar-cell .el-button{margin:0;width:100%;padding:2px 4px;height:20px;font-size:11px}.fallback-select{margin-top:10px;width:100%}
</style>
