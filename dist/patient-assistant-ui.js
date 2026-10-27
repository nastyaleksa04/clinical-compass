state.patientAssistant={status:null,statusLoading:false,query:'',answer:null,clarificationAnswers:{},loading:false,error:null};

async function loadPatientAssistantStatus(){
  const item=state.patientAssistant;if(item.status||item.statusLoading)return;
  item.statusLoading=true;
  try{item.status=await api('/api/patient-assistant/status')}catch(error){item.error=error.message}
  item.statusLoading=false;if(state.view==='patient-assistant')render();
}

function patientAssistantSources(result){
  if(!result?.citations?.length)return '';
  const cited=new Set([...result.answer.matchAll(/\[(\d+)\]/g)].map(match=>Number(match[1])));
  return `<div class='pa-sources'><b>Материалы ответа</b>${result.citations.map(source=>`<details class='pa-source ${cited.has(source.number)?'is-cited':''}'><summary><span>${source.number}</span><div><b>${esc(source.title||source.source_id)}</b><small>${esc(source.evidence?.section||'')}</small></div>${icon('chevron')}</summary><p>${esc(source.excerpt)}</p>${source.url?`<a href='${esc(source.url)}' target='_blank' rel='noreferrer'>Подробнее об источнике</a>`:''}</details>`).join('')}</div>`;
}

function patientClarification(result){
  const data=result?.clarification;if(!data)return '';
  if(result.route==='clarification_confirmation')return `<article class='card pa-clarification'><span class='eyebrow'>Перед сохранением</span><h3>Проверьте ваши ответы</h3><p>${esc(result.answer)}</p><div class='pa-confirm-list'>${data.summary.map(item=>`<div><small>${esc(item.label)}</small><b>${esc(item.answer)}</b></div>`).join('')}</div><div class='pa-confirm-actions'><button class='btn btn-secondary' data-pa-edit>Изменить</button><button class='btn btn-primary' data-pa-confirm>${icon('check')} Подтвердить и получить ответ</button></div></article>`;
  const answers=state.patientAssistant.clarificationAnswers||{};
  return `<form id='pa-clarification-form' class='card pa-clarification'><span class='eyebrow'>Нужно уточнение</span><h3>Несколько коротких вопросов</h3><p>${esc(result.answer)}</p>${data.questions.map(question=>`<label class='pa-question'><span>${esc(question.label)}</span>${question.type==='select'?`<select name='${esc(question.id)}' required><option value=''>Выберите вариант</option>${question.options.map(option=>`<option value='${esc(option.value)}' ${answers[question.id]===option.value?'selected':''}>${esc(option.label)}</option>`).join('')}</select>`:`<input class='text-input' name='${esc(question.id)}' maxlength='500' value='${esc(answers[question.id]||'')}' required>`}</label>`).join('')}<button class='btn btn-primary btn-wide' type='submit'>Продолжить ${icon('arrow')}</button><small>До подтверждения ответы не сохраняются и не отправляются модели.</small></form>`;
}

async function sendPatientAssistant(confirm=false){
  const item=state.patientAssistant;item.loading=true;item.error=null;if(confirm)item.answer=null;render();
  try{
    item.answer=await api('/api/patient-assistant/answer',{method:'POST',body:JSON.stringify({query:item.query,limit:5,clarification_answers:item.clarificationAnswers,confirm_clarification:confirm})});
    if(item.answer.clarification_saved){await loadState();toast('Уточнение подтверждено и добавлено в историю')}
  }catch(error){item.error=error.message}
  item.loading=false;render();
}

function patientAssistantView(){
  const item=state.patientAssistant,status=item.status,result=item.answer;
  const examples=['Что означает мой последний GAD-7?','Какие задачи мне осталось выполнить?','Что указано в моём плане?','Что делать, если я пропустила приём?'];
  const route=result?.route;
  return shell(`<div class='page-head pa-head'><button class='back' data-view='home'>${icon('chevron')}</button><div><span class='eyebrow'>Qwen · пациентская база</span><h2>Помощник</h2><p>Объясняет функции приложения и общие правила наблюдения</p></div></div>
  <div class='notice notice-neutral pa-boundary'>${icon('shield')} Помощник учитывает только видимые вам подтверждённые данные. Он не видит внутренние заметки врача, не ставит диагноз и не меняет лечение.</div>
  ${status&&!status.configured?`<div class='notice notice-warn'>${icon('info')} Помощник временно не подключён. Экстренная маршрутизация и правила терапии продолжают работать без модели.</div>`:''}
  <form id='patient-assistant-form' class='pa-form card'><label for='pa-question'>Ваш вопрос</label><textarea id='pa-question' rows='4' maxlength='2000' placeholder='Например: что показывает GAD-7?'>${esc(item.query)}</textarea><div><small>Не используйте этот чат при непосредственной угрозе жизни</small><button class='btn btn-primary' type='submit' ${item.loading?'disabled':''}>${item.loading?'Отвечаем…':`${icon('sparkles')} Спросить`}</button></div></form>
  ${!result&&!item.loading?`<div class='pa-examples'>${examples.map(value=>`<button data-pa-example='${esc(value)}'>${esc(value)}</button>`).join('')}</div>`:''}
  ${item.loading?`<article class='card pa-loading'><span></span><span></span><span></span> Ищем понятный ответ…</article>`:''}
  ${item.error?`<div class='notice notice-danger'>${icon('warning')} ${esc(item.error)}</div>`:''}
  ${route==='clarification'||route==='clarification_confirmation'?patientClarification(result):result?`<article class='card pa-answer ${route==='emergency'?'is-emergency':route==='contact_doctor'?'is-doctor':''}'><header><span class='pa-answer-icon'>${icon(route==='emergency'?'sos':route==='contact_doctor'?'stethoscope':'message')}</span><div><span class='eyebrow'>${route==='emergency'?'Нужна помощь сейчас':route==='contact_doctor'?'Нужно решение специалиста':result.context_used?'Ответ по вашему плану и данным':'Справочный ответ'}</span><h3>${route==='emergency'?'Не ждите ответа в приложении':route==='contact_doctor'?'Свяжитесь с врачом':'Ответ помощника'}</h3></div></header><div class='pa-answer-text'>${kbText(result.answer)}</div>${route==='emergency'?`<a class='btn btn-danger btn-wide' href='tel:112'>${icon('phone')} Позвонить 112</a>`:''}${route==='contact_doctor'?`<button class='btn btn-primary btn-wide' data-view='messages'>${icon('message')} Написать врачу</button>`:''}${result.clarification_saved?`<div class='notice notice-success'>${icon('check')} Уточнение подтверждено и добавлено в историю.</div>`:''}${result.personal_data_redacted?`<div class='notice notice-neutral'>Контактные данные были скрыты перед обработкой вопроса.</div>`:''}${result.context_used?`<div class='notice notice-neutral'>${icon('shield')} Использованы только данные, доступные вам в приложении.</div>`:''}${result.citation_warnings?.map(value=>`<div class='notice notice-warn'>${esc(value)}</div>`).join('')||''}${patientAssistantSources(result)}<footer>${result.generated_by_llm?esc(result.model||'Qwen'):'Ответ сформирован правилом безопасности'} · ${esc(result.retrieval?.release||'')}</footer><button class='text-btn' data-pa-reset>Задать другой вопрос</button></article>`:''}
  <div class='notice notice-neutral'>При непосредственной угрозе жизни позвоните 112 или обратитесь в ближайшее отделение экстренной помощи.</div>`,'home');
}

const basePatientHomeAI=patientHome;
patientHome=function(){
  const html=basePatientHomeAI();
  const marker='<p class="locate">';
  const banner=`<button class='pa-banner' data-view='patient-assistant'><span class='pa-banner-icon'>${icon('sparkles')}</span><span><b>Умный помощник</b><small>Ответы по опросникам и функциям приложения</small></span>${icon('chevron')}</button>`;
  return html.includes(marker)?html.replace(marker,banner+marker):html;
}

const baseRenderPatientAI=render;
render=function(){
  if(!state.loading&&!state.error&&state.role==='patient'&&state.view==='patient-assistant'){
    if(!state.patientAssistant.status&&!state.patientAssistant.statusLoading)loadPatientAssistantStatus();
    document.querySelector('#app').innerHTML=patientAssistantView();bind();return;
  }
  baseRenderPatientAI();
}

const baseBindPatientAI=bind;
bind=function(){
  baseBindPatientAI();
  document.querySelectorAll('[data-pa-example]').forEach(button=>button.addEventListener('click',()=>{const input=document.querySelector('#pa-question');if(input){input.value=button.dataset.paExample;input.focus()}}));
  document.querySelector('[data-pa-reset]')?.addEventListener('click',()=>{state.patientAssistant.answer=null;state.patientAssistant.error=null;state.patientAssistant.query='';state.patientAssistant.clarificationAnswers={};render()});
  document.querySelector('#pa-clarification-form')?.addEventListener('submit',async event=>{event.preventDefault();const data=new FormData(event.target);state.patientAssistant.clarificationAnswers=Object.fromEntries(data.entries());await sendPatientAssistant(false)});
  document.querySelector('[data-pa-edit]')?.addEventListener('click',()=>{state.patientAssistant.answer.route='clarification';render()});
  document.querySelector('[data-pa-confirm]')?.addEventListener('click',()=>sendPatientAssistant(true));
  document.querySelector('#patient-assistant-form')?.addEventListener('submit',async event=>{
    event.preventDefault();const item=state.patientAssistant;const query=document.querySelector('#pa-question').value.trim();
    if(query.length<3){toast('Введите вопрос не короче трёх символов');return}
    item.query=query;item.clarificationAnswers={};item.answer=null;await sendPatientAssistant(false);
  });
}

// Patient medical record and protected PDF documents.
const patientDocumentsStyles=document.createElement('link');patientDocumentsStyles.rel='stylesheet';patientDocumentsStyles.href='documents.css';document.head.appendChild(patientDocumentsStyles);
state.patientDocuments={items:null,loading:false,error:null,filter:'all'};

async function loadPatientDocuments(){
  const store=state.patientDocuments;if(store.loading)return;
  store.loading=true;store.error=null;
  try{store.items=(await api(`/api/patients/${state.patient.id}/documents`)).documents}catch(error){store.error=error.message}
  store.loading=false;if(state.view==='medcard'||state.view==='documents')render();
}

function documentDate(value){return new Intl.DateTimeFormat('ru-RU',{day:'numeric',month:'long',year:'numeric'}).format(new Date(`${value}T12:00:00`))}
function documentSize(value){return value>1024*1024?`${(value/1024/1024).toFixed(1)} МБ`:`${Math.ceil(value/1024)} КБ`}

function medcardView(){
  const count=state.patientDocuments.items?.length||0;
  const tiles=[['clock','Записи и вызовы','История наблюдения','timeline','records'],['file','Документы',count?`${count} PDF: заключения и анализы`:'Результаты анализов и заключения','documents','documents'],['clipboard','Направления','Обследования и задачи от врача','plan','referrals'],['pill','Назначения','Препараты и рекомендации','plan','prescriptions']];
  return shell(`<div class='page-head medcard-head'><h2>Медкарта</h2><p>Ваши медицинские документы и назначения</p></div><div class='medcard-grid'>${tiles.map(([glyph,title,copy,view,tone])=>`<button class='medcard-tile tone-${tone}' data-view='${view}'><span class='medcard-icon'>${icon(glyph)}</span><span><b>${title}</b><small>${copy}</small></span>${icon('chevron')}</button>`).join('')}</div><div class='notice notice-neutral medcard-privacy'>${icon('lock')} Документы открываются через защищённый локальный API и не размещаются в публичной папке сайта.</div>`,'home');
}

function patientDocumentsView(){
  const store=state.patientDocuments,items=store.items||[];const visible=store.filter==='all'?items:items.filter(item=>item.category===store.filter);
  return shell(`<div class='page-head documents-head'><button class='back' data-view='medcard'>${icon('chevron')}</button><span class='eyebrow'>Медкарта</span><h2>Документы</h2><p>Психиатрические отчёты формируются по актуальной истории пациента</p></div><div class='document-filters'><button class='${store.filter==='all'?'active':''}' data-document-filter='all'>Все <span>${items.length}</span></button><button class='${store.filter==='visit_report'?'active':''}' data-document-filter='visit_report'>Приём <span>${items.filter(x=>x.category==='visit_report').length}</span></button><button class='${store.filter==='monitoring_report'?'active':''}' data-document-filter='monitoring_report'>Динамика <span>${items.filter(x=>x.category==='monitoring_report').length}</span></button></div>${store.loading?`<article class='card pa-loading'><span></span><span></span><span></span> Подготавливаем список отчётов…</article>`:''}${store.error?`<div class='notice notice-danger'>${icon('warning')} ${esc(store.error)}</div>`:''}${!store.loading&&!store.error?`<div class='document-list'>${visible.map(item=>`<article class='document-card'><span class='document-icon ${item.category==='monitoring_report'?'is-lab':''}'>${icon(item.category==='monitoring_report'?'activity':'file')}</span><div class='document-copy'><span class='eyebrow'>${item.category==='monitoring_report'?'Результаты наблюдения':'Отчёт приёма'}</span><h3>${esc(item.title)}</h3><p>${esc(item.specialty)}</p><small>${esc(item.description)} · актуально на ${fmtDate(item.generated_at)}</small></div><button class='btn btn-secondary' data-open-document='${esc(item.id)}'>${icon('file')} Сформировать PDF</button></article>`).join('')||`<article class='card empty'><span class='status-orb'>${icon('file')}</span><h3>Отчётов нет</h3><p>Для формирования отчёта нужна карточка пациента.</p></article>`}</div>`:''}<div class='notice notice-neutral document-note'>${icon('info')} PDF создаётся в момент открытия из текущих данных карты. Это черновик, который должен проверить врач.</div>`,'home');
}

async function openPatientDocument(documentId){
  const popup=window.open('about:blank','_blank');
  try{const response=await fetch(`/api/patients/${state.patient.id}/documents/${encodeURIComponent(documentId)}/file`,{headers:{'X-Demo-Role':'patient'}});if(!response.ok){let message='Не удалось сформировать документ';try{message=(await response.json()).detail||message}catch{}throw new Error(message)}const url=URL.createObjectURL(await response.blob());if(popup)popup.location.href=url;else{const link=document.createElement('a');link.href=url;link.target='_blank';link.click()}setTimeout(()=>URL.revokeObjectURL(url),120000)}catch(error){if(popup)popup.close();toast(error.message)}
}

const basePatientHomeDocuments=patientHome;
patientHome=function(){let html=basePatientHomeDocuments();const marker='<div class="content-columns">';const entry=`<section class='medcard-entry'><button data-view='medcard'><span class='medcard-icon'>${icon('file')}</span><span><b>Моя медкарта</b><small>Заключения врачей, анализы и назначения</small></span>${icon('chevron')}</button></section>`;return html.includes(marker)?html.replace(marker,entry+marker):html}

const baseRenderDocuments=render;
render=function(){if(!state.loading&&!state.error&&state.role==='patient'&&(state.view==='medcard'||state.view==='documents')){if(!state.patientDocuments.items&&!state.patientDocuments.loading)loadPatientDocuments();document.querySelector('#app').innerHTML=state.view==='medcard'?medcardView():patientDocumentsView();bind();return}baseRenderDocuments()}

const baseBindDocuments=bind;
bind=function(){baseBindDocuments();document.querySelectorAll('[data-document-filter]').forEach(button=>button.addEventListener('click',()=>{state.patientDocuments.filter=button.dataset.documentFilter;render()}));document.querySelectorAll('[data-open-document]').forEach(button=>button.addEventListener('click',()=>openPatientDocument(button.dataset.openDocument)))}
