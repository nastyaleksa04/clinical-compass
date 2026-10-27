state.ragAssistant={status:null,statusLoading:false,query:'',answer:null,loading:false,error:null};

function ragLocation(evidence={}){
  const value=evidence.page||evidence.pages||evidence.section;
  if(!value)return '';
  return Array.isArray(value)?value.join(', '):String(value);
}

async function loadRagStatus(){
  const assistant=state.ragAssistant;
  if(assistant.statusLoading||assistant.status)return;
  assistant.statusLoading=true;
  try{assistant.status=await api('/api/rag/status')}catch(error){assistant.error=error.message}
  assistant.statusLoading=false;
  if(state.view==='knowledge')render();
}

function ragSources(result){
  if(!result?.citations?.length)return '';
  const cited=new Set([...result.answer.matchAll(/\[(\d+)\]/g)].map(match=>Number(match[1])));
  return `<div class='rag-sources'><h4>Фрагменты базы знаний</h4>${result.citations.map(source=>{
    const location=ragLocation(source.evidence);
    return `<details class='rag-source ${cited.has(source.number)?'is-cited':''}'><summary><span>${source.number}</span><div><b>${esc(source.title||source.source_id)}</b><small>${esc([source.organization,location&&('стр./раздел '+location)].filter(Boolean).join(' · '))}</small></div>${icon('chevron')}</summary><p>${esc(source.excerpt)}</p>${source.url?`<a href='${esc(source.url)}' target='_blank' rel='noreferrer'>${icon('book')} Открыть источник</a>`:''}</details>`;
  }).join('')}</div>`;
}

function ragAssistantPanel(){
  const assistant=state.ragAssistant;
  const status=assistant.status;
  const examples=['Критерии высокого суицидального риска','Как оценивать динамику по HDRS-17?','Какие ограничения есть у маритупирдина?'];
  const statusLabel=assistant.statusLoading?'Проверяем подключение':status?.configured?`OpenRouter · ${esc(status.model)}`:'OpenRouter не подключён';
  return `<section class='rag-assistant card'>
    <div class='rag-assistant-head'><div class='rag-orb'>${icon('sparkles')}</div><div><span class='eyebrow'>RAG · KB v2.2</span><h3>Ассистент врача</h3><p>Ответы по врачебному корпусу с указанием найденных фрагментов</p></div><span class='rag-status ${status?.configured?'is-ready':''}'>${statusLabel}</span></div>
    ${status&&!status.configured?`<div class='notice notice-neutral'>${icon('info')} Скопируйте <b>.env.example</b> в <b>.env</b>, добавьте <b>OPENROUTER_API_KEY</b> и перезапустите сервер.</div>`:''}
    <form id='rag-assistant-form' class='rag-form'>
      <textarea id='rag-question' rows='3' maxlength='2000' placeholder='Задайте клинический вопрос по базе знаний…' ${status&&!status.configured?'disabled':''}>${esc(assistant.query)}</textarea>
      <div class='rag-form-actions'><span>Без персональных данных · проверка врача</span><button class='btn btn-primary' type='submit' ${assistant.loading||!status?.configured?'disabled':''}>${assistant.loading?'Формируем…':`${icon('sparkles')} Спросить`}</button></div>
    </form>
    ${!assistant.answer&&!assistant.loading?`<div class='rag-examples'>${examples.map(value=>`<button type='button' data-rag-example='${esc(value)}' ${!status?.configured?'disabled':''}>${esc(value)}</button>`).join('')}</div>`:''}
    ${assistant.error?`<div class='notice notice-danger'>${icon('warning')} ${esc(assistant.error)}</div>`:''}
    ${assistant.loading?`<div class='rag-thinking'><span></span><span></span><span></span> Ищем источники и формируем ответ…</div>`:''}
    ${assistant.answer?`<article class='rag-answer'><div class='rag-answer-title'><b>Ответ</b><span class='badge ${assistant.answer.grounded?'badge-new':'badge-warn'}'>${assistant.answer.grounded?'Номера ссылок корректны':'Проверьте ссылки'}</span></div><div class='rag-answer-text'>${kbText(assistant.answer.answer)}</div>${assistant.answer.citation_warnings?.map(item=>`<div class='notice notice-warn'>${icon('warning')} ${esc(item)}</div>`).join('')||''}${ragSources(assistant.answer)}<footer><span>${esc(assistant.answer.model||'')}</span><span>${esc(assistant.answer.retrieval?.release||'')}</span></footer></article>`:''}
  </section>`;
}

const baseKnowledgeViewRagAssistant=knowledgeView;
knowledgeView=function(){
  const html=baseKnowledgeViewRagAssistant();
  const marker='<label class="search-bar">';
  return html.includes(marker)?html.replace(marker,ragAssistantPanel()+marker):html;
}

const baseRenderRagAssistant=render;
render=function(){
  if(!state.loading&&!state.error&&state.role==='doctor'&&state.view==='knowledge'&&!state.ragAssistant.status&&!state.ragAssistant.statusLoading)loadRagStatus();
  baseRenderRagAssistant();
}

const baseBindRagAssistant=bind;
bind=function(){
  baseBindRagAssistant();
  document.querySelectorAll('[data-rag-example]').forEach(button=>button.addEventListener('click',()=>{
    const input=document.querySelector('#rag-question');if(input){input.value=button.dataset.ragExample;input.focus()}
  }));
  document.querySelector('#rag-assistant-form')?.addEventListener('submit',async event=>{
    event.preventDefault();
    const assistant=state.ragAssistant;
    const query=document.querySelector('#rag-question').value.trim();
    if(query.length<3){toast('Введите вопрос не короче трёх символов');return}
    assistant.query=query;assistant.loading=true;assistant.error=null;assistant.answer=null;render();
    try{assistant.answer=await api('/api/rag/answer',{method:'POST',body:JSON.stringify({query,limit:6})})}catch(error){assistant.error=error.message}
    assistant.loading=false;render();
  });
}