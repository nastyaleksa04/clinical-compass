function renderAiSummaryText(value){
 const lines=String(value||'').replace(/\r/g,'').split('\n');
 const known=/^(Клинический обзор|Динамика состояния|Риски и клиническое внимание|Что уточнить на следующем контакте|Недостающие данные)\s*:?$/i;
 let html='',list=false;
 function closeList(){if(list){html+='</ul>';list=false}}
 function inline(text){return esc(text).replace(/\*\*([^*]+)\*\*/g,'<strong>$1</strong>').replace(/\[(\d+)\]/g,'<span class="ai-citation">[$1]</span>')}
 lines.forEach(function(raw){
  const line=raw.trim();
  if(!line){closeList();return}
  const heading=line.match(/^#{1,3}\s+(.+)$/)||line.match(known);
  if(heading){closeList();html+='<h3>'+inline(heading[1])+'</h3>';return}
  const bullet=line.match(/^[-*•]\s+(.+)$/);
  if(bullet){if(!list){html+='<ul>';list=true}html+='<li>'+inline(bullet[1])+'</li>';return}
  closeList();html+='<p>'+inline(line)+'</p>'
 });
 closeList();
 return html
}
function confirmedAiSummary(saved){
 if(!saved)return '';
 return '<div class="confirmed-ai-summary"><div class="confirmed-ai-head"><span>'+icon('check')+'</span><div><b>Проверено врачом</b><small>'+fmtDate(saved.created_at)+' · '+esc(saved.confirmed_by)+'</small></div></div><div class="ai-summary-text">'+renderAiSummaryText(saved.final_text)+'</div><details><summary>Происхождение записи</summary><p>AI-черновик: '+esc(saved.model||'модель не указана')+' · база '+esc(saved.retrieval_release||'не указана')+' · источников: '+(saved.citations||[]).length+'</p></details></div>'
}
function aiSummaryBlock(){
 const current=state.currentPatient;
 const item=state.aiClinicalSummary;
 const matches=item&&item.patientId===current?.id;
 const loading=matches&&item.loading;
 const data=matches&&item.data;
 const editing=Boolean(matches&&item.editing);
 const error=matches&&item.error;
 const citations=data?.citations||[];
 const saved=(state.aiSummaries||[])[0];
 return '<section class="section ai-summary-section" id="patient-ai-summary"><article class="card ai-summary-card"><div class="section-head"><div><p class="eyebrow">Qwen + врачебная база знаний</p><h2>AI-сводка по случаю</h2></div><span class="badge '+(saved&&!data?'badge-new':'badge-warn')+'">'+(saved&&!data?'Проверено':'Черновик')+'</span></div><p class="ai-summary-intro">Сводка собирает динамику, риски и недостающие данные. В историю попадает только версия, которую проверил и явно подтвердил врач.</p>'
  +(loading?'<div class="ai-summary-loading"><span class="status-orb">'+icon('sparkles')+'</span><div><b>Анализируем данные</b><p>Обезличиваем карту и сопоставляем её с базой знаний…</p></div></div>':'')
  +(error?'<div class="notice notice-danger">'+icon('warning')+' <span>'+esc(error)+'</span></div>':'')
  +(data?'<div class="ai-summary-meta"><span>'+icon('shield')+' Данные обезличены</span><span>'+icon(data.grounded?'check':'warning')+' '+(data.grounded?'Ссылки проверены':'Нужна проверка ссылок')+'</span><span>'+esc(data.model||'модель')+'</span></div>'
    +(editing?'<div class="field ai-summary-editor"><label for="ai-summary-edit">Текст после проверки врача</label><textarea id="ai-summary-edit" rows="22" maxlength="20000">'+esc(item.text||data.summary)+'</textarea><small>Можно исправить формулировки, убрать лишнее и добавить клинический контекст перед сохранением.</small></div>':'<div class="ai-summary-text">'+renderAiSummaryText(data.summary)+'</div>')
    +(data.citation_warnings||[]).map(function(x){return '<div class="notice notice-warn">'+icon('warning')+' <span>'+esc(x)+'</span></div>'}).join('')
    +(citations.length?'<details class="ai-summary-sources"><summary>Источники базы знаний · '+citations.length+'</summary><div>'+citations.map(function(x){return '<article><b>['+x.number+'] '+esc(x.title||x.source_id)+'</b><p>'+esc(x.excerpt||'')+'</p>'+(x.url?'<a href="'+esc(x.url)+'" target="_blank" rel="noreferrer">Открыть источник</a>':'')+'</article>'}).join('')+'</div></details>':'')
   :(!loading?confirmedAiSummary(saved):''))
  +'<div class="ai-summary-actions"><button class="btn btn-secondary" id="generate-ai-summary" '+(loading?'disabled':'')+'>'+icon('sparkles')+' '+(data?'Сформировать заново':'Сформировать AI-сводку')+'</button>'
  +(data?(editing?'<button class="btn btn-secondary" id="cancel-ai-edit">Отменить правки</button>':'<button class="btn btn-secondary" id="edit-ai-summary">'+icon('edit')+' Редактировать</button>')+'<button class="btn btn-primary" id="confirm-ai-summary">'+icon('check')+' Подтвердить и сохранить</button>':'')
  +'<span>'+(data?'Сохранится только после подтверждения':'AI не меняет карту автоматически')+'</span></div></article></section>'
}
const basePatientDetailAiSummary=patientDetail;
patientDetail=function(){
 let html=basePatientDetailAiSummary();
 if(state.role!=='doctor'||!state.currentPatient)return html;
 html=html.replace('<button data-patient-jump="patient-recommendations"', '<button data-patient-jump="patient-ai-summary">'+icon('sparkles')+' AI-сводка</button><button data-patient-jump="patient-recommendations"');
 const anchor='<section class="section recommendation-section" id="patient-recommendations">';
 return html.includes(anchor)?html.replace(anchor,aiSummaryBlock()+anchor):html.replace('<section class="section clinical-section" id="patient-clinical">',aiSummaryBlock()+'<section class="section clinical-section" id="patient-clinical">')
};
const baseOpenPatientAiSummary=openPatient;
openPatient=async function(id){
 if(state.aiClinicalSummary?.patientId!==id)state.aiClinicalSummary=null;
 return baseOpenPatientAiSummary(id)
};
const baseBindAiSummary=bind;
bind=function(){
 baseBindAiSummary();
 document.querySelector('#generate-ai-summary')?.addEventListener('click',async function(){
  const patientId=state.currentPatient?.id;
  if(!patientId)return;
  state.aiClinicalSummary={patientId:patientId,loading:true,data:null,error:null,editing:false,text:''};
  render();
  try{
   const data=await api('/api/patients/'+patientId+'/ai-summary',{method:'POST',body:JSON.stringify({limit:6})});
   state.aiClinicalSummary={patientId:patientId,loading:false,data:data,error:null,editing:false,text:data.summary};
   render();
   document.querySelector('#patient-ai-summary')?.scrollIntoView({behavior:'smooth',block:'start'})
  }catch(error){
   state.aiClinicalSummary={patientId:patientId,loading:false,data:null,error:error.message,editing:false,text:''};
   render()
  }
 });
 document.querySelector('#edit-ai-summary')?.addEventListener('click',function(){
  state.aiClinicalSummary.editing=true;state.aiClinicalSummary.text=state.aiClinicalSummary.data.summary;render();
  requestAnimationFrame(()=>document.querySelector('#ai-summary-edit')?.focus())
 });
 document.querySelector('#cancel-ai-edit')?.addEventListener('click',function(){
  state.aiClinicalSummary.editing=false;state.aiClinicalSummary.text=state.aiClinicalSummary.data.summary;render()
 });
 document.querySelector('#confirm-ai-summary')?.addEventListener('click',async function(){
  const item=state.aiClinicalSummary,data=item?.data,patientId=state.currentPatient?.id;
  if(!data||!patientId)return;
  const field=document.querySelector('#ai-summary-edit');
  const content=(field?field.value:item.text||data.summary).trim();
  if(content.length<20)return toast('Сводка слишком короткая');
  const button=this;button.disabled=true;
  try{
   await api('/api/patients/'+patientId+'/ai-summaries/confirm',{method:'POST',body:JSON.stringify({
    content:content,draft_text:data.summary,model:data.model||'',
    retrieval_release:data.retrieval?.release||'',citations:data.citations||[]
   })});
   state.aiClinicalSummary=null;
   await openPatient(patientId);
   requestAnimationFrame(()=>document.querySelector('#patient-ai-summary')?.scrollIntoView({block:'start'}));
   toast('Проверенная сводка сохранена в историю')
  }catch(error){button.disabled=false;toast(error.message)}
 })
};
