// Нейрон — AI-помощник. У пациента его настроение отражает регулярность наблюдения (app/neuron.py).

const NEURON_MOODS=['sad','sleepy','calm','cozy','blooming','excited'];
function neuronImg(mood,cls='neuron-img'){return `<img class="${cls}" src="assets/neuron/${NEURON_MOODS.includes(mood)?mood:'calm'}.png" alt="" draggable="false">`}
function neuronKey(){return state.role==='doctor'?`doctor:${state.currentPatient?.id||''}`:'patient'}
function neuronPath(){return state.role==='doctor'?`/api/patients/${state.currentPatient.id}/neuron`:'/api/neuron'}

async function loadNeuron(){
  const key=neuronKey();
  if(state.neuronLoadingKey===key)return;
  state.neuronLoadingKey=key;
  try{state.neuron=await baseApiNeuron(neuronPath());state.neuronKey=key;state.neuronError=''}
  catch(error){state.neuronError=error.message;state.neuronKey=key}
  finally{state.neuronLoadingKey=null}
  render();
}
function neuronData(){
  if(state.neuronKey===neuronKey())return state.neuron;
  loadNeuron();
  return null;
}

function neuronChip(previous,current){
  let node=document.querySelector('#neuron-chip');
  if(!node){node=document.createElement('div');node.id='neuron-chip';node.className='neuron-chip';node.setAttribute('role','status');document.body.appendChild(node)}
  const up=previous&&current.rank>previous.rank;
  node.innerHTML=`${neuronImg(current.mood,'neuron-chip-img')}<span><b>${up?'Нейрон повеселел!':'Нейрону приятно'}</b><small>${esc(up?current.title:'Отметка учтена · бодрость '+current.score+'%')}</small></span>`;
  node.classList.add('show');
  clearTimeout(neuronChip.timer);neuronChip.timer=setTimeout(()=>node.classList.remove('show'),3200);
}

const baseApiNeuron=api;
api=async function(path,options={}){
  const data=await baseApiNeuron(path,options);
  const method=(options.method||'GET').toUpperCase();
  const tracked=/\/(reports|assessments|medication-checkins|drug-reports)$/.test(path)||(/^\/api\/tasks\/\d+$/.test(path)&&data?.status==='completed');
  if(state.role==='patient'&&method!=='GET'&&tracked){
    const previous=state.neuronKey==='patient'?state.neuron:null;
    baseApiNeuron('/api/neuron').then(current=>{state.neuron=current;state.neuronKey='patient';neuronChip(previous,current)}).catch(()=>{state.neuronKey=null});
  }
  return data;
};

function neuronMeter(data){return `<div class="neuron-meter" role="meter" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${data.score}" aria-label="Бодрость Нейрона"><i style="width:${Math.max(4,data.score)}%"></i></div>`}

function neuronWeek(data){
  const day=value=>new Intl.DateTimeFormat('ru-RU',{weekday:'short'}).format(new Date(`${value}T12:00:00`));
  return `<div class="neuron-week">${data.week.map(item=>`<div class="neuron-day ${item.active?'is-active':''}"><span>${day(item.date)}</span>
    <i class="nd nd-report ${item.report?'on':''}" title="Самоотчёт"></i>
    ${data.has_therapy?`<i class="nd nd-dose ${item.medication==='taken'?'on':item.medication==='missed'?'half':''}" title="Терапия"></i>`:''}
    <i class="nd nd-scale ${item.assessment?'on':''}" title="Опросник"></i>
    <i class="nd nd-drug ${item.drug?'on':''}" title="Анкета о препарате"></i></div>`).join('')}</div>
    <div class="neuron-legend"><span><i class="nd nd-report on"></i>Самоотчёт</span>${data.has_therapy?'<span><i class="nd nd-dose on"></i>Приём</span><span><i class="nd nd-dose half"></i>Отмечен пропуск</span>':''}<span><i class="nd nd-scale on"></i>Опросник</span><span><i class="nd nd-drug on"></i>Анкета о препарате</span></div>`;
}

function neuronToday(data,compact){
  const items=compact?data.today.filter(item=>!item.done):data.today;
  if(!items.length)return `<p class="neuron-done">${icon('check')} На сегодня всё отмечено — Нейрон доволен</p>`;
  return `<div class="neuron-todo ${compact?'is-compact':''}">${items.map(item=>`<button class="neuron-task is-${item.id} ${item.done?'is-done':''}" data-view="${item.view}" ${item.done?'disabled':''}><span class="neuron-tick">${item.done?icon('check'):''}</span><span><b>${esc(item.title)}</b><small>${esc(item.hint)}</small></span>${item.done?'':icon('chevron')}</button>`).join('')}</div>`;
}

function neuronHomeCard(){
  const data=neuronData();
  if(!data)return `<section class="neuron-card is-loading">${neuronImg('calm')}<div class="neuron-card-text"><span class="eyebrow">Ваш ИИ-помощник</span><b>Нейрон просыпается…</b></div></section>`;
  return `<section class="neuron-card mood-${data.mood}">
    <button class="neuron-card-main" data-view="neuron" aria-label="Открыть Нейрона">${neuronImg(data.mood)}
      <span class="neuron-card-text"><span class="eyebrow">Ваш ИИ-помощник · ${esc(data.name)}</span><b>${esc(data.title)}</b><small>${esc(data.message)}</small>
      ${neuronMeter(data)}<span class="neuron-stats"><span>Бодрость <b>${data.score}%</b></span><span>Серия <b>${data.streak} дн.</b></span></span></span></button>
    <div class="neuron-card-side"><span class="neuron-side-title">Что порадует Нейрона</span>${neuronToday(data,true)}
      <button class="btn btn-secondary neuron-ask" data-view="patient-assistant">${icon('sparkles')} Спросить Нейрона</button></div>
  </section>`;
}

function neuronView(){
  const data=neuronData();
  const body=!data?`<article class="card neuron-loading">${state.neuronError?esc(state.neuronError):'Нейрон просыпается…'}</article>`:`
  <section class="neuron-hero mood-${data.mood}">${neuronImg(data.mood,'neuron-hero-img')}
    <div><span class="eyebrow">Настроение сегодня</span><h3>${esc(data.title)}</h3><p>${esc(data.message)}</p>${neuronMeter(data)}
    <div class="neuron-stats"><span>Бодрость <b>${data.score}%</b></span><span>Серия <b>${data.streak} дн.</b></span>${data.idle_days?`<span>Без отметок <b>${data.idle_days} дн.</b></span>`:''}</div>
    <button class="btn btn-primary" data-view="patient-assistant">${icon('sparkles')} Спросить Нейрона</button></div></section>
  <section class="card"><div class="section-head"><div><p class="eyebrow">Сегодня</p><h2>Что порадует Нейрона</h2></div></div>${neuronToday(data,false)}</section>
  <section class="card"><div class="section-head"><div><p class="eyebrow">Последние 7 дней</p><h2>Ритм наблюдения</h2></div></div>${neuronWeek(data)}</section>
  <section class="card"><div class="section-head"><div><p class="eyebrow">Шесть состояний</p><h2>Как меняется Нейрон</h2></div></div>
    <div class="neuron-moods">${data.moods.slice().reverse().map(item=>`<div class="neuron-mood ${item.id===data.mood?'is-current':''}">${neuronImg(item.id,'neuron-mood-img')}<b>${esc(item.title)}</b>${item.id===data.mood?'<small>Сейчас</small>':''}</div>`).join('')}</div></section>
  <section class="card neuron-rules"><div class="section-head"><div><p class="eyebrow">Честные правила</p><h2>От чего зависит настроение</h2></div></div><ul>${data.principles.map(text=>`<li>${esc(text)}</li>`).join('')}</ul></section>`;
  return shell(`<div class="page-head"><button class="back" data-view="home">${icon('chevron')}</button><div><span class="eyebrow">Ваш ИИ-помощник</span><h2>Нейрон</h2><p>Растёт вместе с регулярностью вашего наблюдения</p></div></div>${body}`,'home');
}

function neuronDoctorSection(){
  const data=neuronData();
  const head=`<div class="section-head"><div class="neuron-titled">${neuronImg(data?.mood||'calm','neuron-avatar')}<div><p class="eyebrow">Нейрон пациента</p><h2>Вовлечённость в наблюдение</h2></div></div>${data?`<span class="badge ${data.rank<=1?'badge-warn':'badge-new'}">${esc(data.title)}</span>`:''}</div>`;
  if(!data)return `<section class="card neuron-doctor-section">${head}<p class="muted">${state.neuronError?esc(state.neuronError):'Загружаем…'}</p></section>`;
  return `<section class="card neuron-doctor-section">${head}
    <div class="neuron-doctor-stats"><div><b>${data.score}%</b><span>регулярность за 7 дней</span></div><div><b>${data.streak}</b><span>дней подряд</span></div><div class="${data.idle_days>=3?'is-alert':''}"><b>${data.idle_days??'—'}</b><span>дней без отметок</span></div>${data.has_therapy?`<div class="${data.missed_recent>=3?'is-alert':''}"><b>${data.missed_recent}</b><span>отмеченных пропусков</span></div>`:''}</div>
    ${neuronWeek(data)}<p class="neuron-note">${icon('info')} Показывает только регулярность отметок пациента, а не тяжесть состояния. Ответы и баллы на настроение Нейрона не влияют.</p></section>`;
}

const basePatientHomeNeuron=patientHome;
patientHome=function(){
  const html=basePatientHomeNeuron();
  const card=`<div class="neuron-row">${neuronHomeCard()}${typeof drugSurveyHomeCard==='function'?drugSurveyHomeCard():''}</div>`;
  const banner=/<button class='pa-banner'[\s\S]*?<\/button>/;
  if(banner.test(html))return html.replace(banner,card);
  return html.replace('<p class="locate">',card+'<p class="locate">');
};

const basePatientDetailNeuron=patientDetail;
patientDetail=function(){
  const html=basePatientDetailNeuron();
  return html.includes('<!--/sheet-->')?html.replace('<!--/sheet-->',neuronDoctorSection()+'<!--/sheet-->'):html;
};

function decorateNeuron(){
  const mood=state.role==='patient'&&state.neuronKey==='patient'&&state.neuron?state.neuron.mood:'calm';
  const titled=(node,eyebrowPrefix,img)=>{
    if(!node||node.classList.contains('neuron-titled'))return;
    const inner=document.createElement('div');inner.innerHTML=node.innerHTML;node.innerHTML='';node.classList.add('neuron-titled');
    node.insertAdjacentHTML('afterbegin',img);node.appendChild(inner);
    const eyebrow=inner.querySelector('.eyebrow');if(eyebrow&&eyebrowPrefix)eyebrow.textContent=eyebrowPrefix+eyebrow.textContent;
    return inner;
  };
  document.querySelectorAll('.ai-summary-section,.case-assistant-section').forEach(section=>titled(section.querySelector('.section-head>div:first-child'),'Нейрон · ',neuronImg('calm','neuron-avatar')));
  document.querySelectorAll('.rag-orb:not(.is-neuron)').forEach(node=>{node.classList.add('is-neuron');node.innerHTML=neuronImg('calm','neuron-avatar is-large')});
  document.querySelectorAll('.rag-assistant-head h3').forEach(node=>{if(node.textContent==='Ассистент врача')node.textContent='Нейрон · ассистент врача'});
  const head=document.querySelector('.pa-head');
  if(head&&!head.querySelector('.neuron-avatar')){
    const inner=titled(head.querySelector('.back+div'),'',neuronImg(mood,'neuron-avatar is-large'));
    const title=inner?.querySelector('h2');if(title)title.textContent='Нейрон';
    const eyebrow=inner?.querySelector('.eyebrow');if(eyebrow)eyebrow.textContent='Ваш ИИ-помощник · Qwen';
  }
  document.querySelectorAll('.pa-answer:not(.is-emergency):not(.is-doctor) .pa-answer-icon').forEach(node=>{node.classList.add('is-neuron');node.innerHTML=neuronImg(mood,'neuron-avatar')});
  document.querySelectorAll('.pa-answer h3').forEach(node=>{if(node.textContent==='Ответ помощника')node.textContent='Ответ Нейрона'});
}

const baseRenderNeuron=render;
render=function(){
  if(!state.loading&&!state.error&&state.role==='patient'&&state.view==='neuron'){
    document.querySelector('#app').innerHTML=neuronView();bind();return;
  }
  baseRenderNeuron();
  decorateNeuron();
};
