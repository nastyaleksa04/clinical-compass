function caseAssistantBlock(){
 const item=state.caseAssistant;
 const matches=item&&item.patientId===state.currentPatient?.id;
 const loading=matches&&item.loading;
 const data=matches&&item.data;
 const error=matches&&item.error;
 const question=matches?item.question:'';
 const suggestions=['Как изменилась симптоматика за период наблюдения?','Какие данные требуют проверки сейчас?','Что может объяснять ухудшение состояния?','Каких данных не хватает перед клиническим решением?'];
 return '<section class="section case-assistant-section" id="patient-case-assistant"><article class="card case-assistant-card"><div class="section-head"><div><p class="eyebrow">Контекст открытого пациента</p><h2>Помощник врача по случаю</h2></div><span class="badge badge-new">RAG</span></div><p class="case-assistant-intro">Задайте вопрос о динамике, рисках или пробелах в данных. Помощник даст краткий вывод и выделит только факты, важные для ответа.</p><div class="case-question-chips">'+suggestions.map(function(x){return '<button type="button" data-case-question="'+esc(x)+'">'+esc(x)+'</button>'}).join('')+'</div><form class="case-assistant-form" id="case-assistant-form"><label class="search-bar">'+icon('message')+'<input id="case-assistant-question" maxlength="2000" placeholder="Например: как изменилась тревога за время наблюдения?" value="'+esc(question)+'"></label><button class="btn btn-primary" type="submit" '+(loading?'disabled':'')+'>'+icon('sparkles')+' '+(loading?'Анализируем…':'Спросить')+'</button></form>'
  +(error?'<div class="notice notice-danger">'+icon('warning')+' <span>'+esc(error)+'</span></div>':'')
  +(loading?'<div class="case-assistant-loading"><span class="status-orb">'+icon('brain')+'</span><div><b>Сопоставляем данные случая</b><p>Ищем подтверждения во врачебной базе знаний…</p></div></div>':'')
  +(data?'<div class="case-answer-head"><div><span>'+icon('shield')+'</span><b>Обезличенный ответ</b></div><small>'+esc(data.model||'модель')+'</small></div><div class="ai-summary-text case-answer">'+renderAiSummaryText(data.answer)+'</div>'
    +(data.citation_warnings||[]).map(function(x){return '<div class="notice notice-warn">'+icon('warning')+' <span>'+esc(x)+'</span></div>'}).join('')
    +((data.citations||[]).length?'<details class="ai-summary-sources"><summary>Использованные источники · '+data.citations.length+'</summary><div>'+data.citations.map(function(x){return '<article><b>['+x.number+'] '+esc(x.title||x.source_id)+'</b><p>'+esc(x.excerpt||'')+'</p>'+(x.url?'<a href="'+esc(x.url)+'" target="_blank" rel="noreferrer">Открыть источник</a>':'')+'</article>'}).join('')+'</div></details>':'')
    +'<div class="notice notice-neutral">'+icon('info')+' <span>Ответ является черновиком для врача и не меняет диагноз, терапию или маршрутизацию.</span></div>':'')
  +'</article></section>'
}
const basePatientDetailCaseAssistant=patientDetail;
patientDetail=function(){
 let html=basePatientDetailCaseAssistant();
 if(state.role!=='doctor'||!state.currentPatient)return html;
 html=html.replace('<button data-patient-jump="patient-ai-summary"', '<button data-patient-jump="patient-case-assistant">'+icon('brain')+' Вопрос по случаю</button><button data-patient-jump="patient-ai-summary"');
 const anchor='<section class="section recommendation-section" id="patient-recommendations">';
 return html.includes(anchor)?html.replace(anchor,caseAssistantBlock()+anchor):html.replace('<!--/sheet-->',caseAssistantBlock()+'<!--/sheet-->')
};
const baseOpenPatientCaseAssistant=openPatient;
openPatient=async function(id){
 if(state.caseAssistant?.patientId!==id)state.caseAssistant=null;
 return baseOpenPatientCaseAssistant(id)
};
const baseBindCaseAssistant=bind;
bind=function(){
 baseBindCaseAssistant();
 document.querySelectorAll('[data-case-question]').forEach(function(button){
  button.addEventListener('click',function(){
   const input=document.querySelector('#case-assistant-question');
   if(input){input.value=button.dataset.caseQuestion;input.focus()}
  })
 });
 document.querySelector('#case-assistant-form')?.addEventListener('submit',async function(event){
  event.preventDefault();
  const patientId=state.currentPatient?.id;
  const question=event.target.querySelector('#case-assistant-question').value.trim();
  if(!patientId||question.length<3)return toast('Введите вопрос по случаю');
  state.caseAssistant={patientId:patientId,question:question,loading:true,data:null,error:null};
  render();
  try{
   const data=await api('/api/patients/'+patientId+'/case-assistant/answer',{method:'POST',body:JSON.stringify({question:question,limit:6})});
   state.caseAssistant={patientId:patientId,question:question,loading:false,data:data,error:null};
   render();
   document.querySelector('#patient-case-assistant')?.scrollIntoView({behavior:'smooth',block:'start'})
  }catch(error){
   state.caseAssistant={patientId:patientId,question:question,loading:false,data:null,error:error.message};
   render()
  }
 })
};
