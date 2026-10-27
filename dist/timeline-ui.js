state.timelineFilter='all';

const TIMELINE_META={
  report:{icon:'heart',label:'Самоотчёты'},
  assessment:{icon:'clipboard',label:'Опросники'},
  checkin:{icon:'pill',label:'Терапия'},
  therapy_decision:{icon:'shield',label:'Решение врача'},
  plan:{icon:'list',label:'План'},
  task:{icon:'calendar',label:'План'},
  routing:{icon:'warning',label:'Безопасность'},
  alert:{icon:'bell',label:'Безопасность'},
  clinical:{icon:'stethoscope',label:'Записи врача'},
  ai_summary:{icon:'sparkles',label:'AI-сводка'}
  ,assistant_intake:{icon:'message',label:'Уточнение пациента'}
};
const TIMELINE_FILTERS=[
  ['all','Все'],
  ['assessment','Опросники'],
  ['monitoring','Самоотчёты'],
  ['therapy','Терапия'],
  ['plan','План'],
  ['safety','Риски'],
  ['clinical','Записи врача']
];

function timelineDate(value,full=false){
  const options=full?{day:'numeric',month:'long',year:'numeric'}:{day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'};
  return new Intl.DateTimeFormat('ru-RU',options).format(new Date(value));
}
function timelineEvents(){
  return (state.timeline||[]).filter(item=>state.timelineFilter==='all'||item.category===state.timelineFilter);
}
function timelineItem(item){
  const meta=TIMELINE_META[item.type]||{icon:'activity',label:'Событие'};
  return `<article class="timeline-item tone-${esc(item.tone)}" data-timeline-category="${esc(item.category)}">
    <div class="timeline-marker">${icon(meta.icon)}</div>
    <div class="timeline-copy"><div class="timeline-meta"><span>${esc(meta.label)}</span><time>${timelineDate(item.created_at)}</time></div>
      <div class="timeline-title"><h3>${esc(item.title)}</h3><i>${esc(item.status)}</i></div>
      <p>${esc(item.summary)}</p>${item.details?`<small>${esc(item.details)}</small>`:''}
    </div>
  </article>`;
}
function timelineList(items){
  if(!items.length)return '<div class="empty compact"><span class="status-orb">'+icon('activity')+'</span><h3>Событий пока нет</h3><p>Они появятся после самоотчётов, опросников или действий врача.</p></div>';
  let previous='';
  return `<div class="timeline-list">${items.map(item=>{
    const day=timelineDate(item.created_at,true);
    const heading=day!==previous?`<div class="timeline-day">${day}</div>`:'';
    previous=day;return heading+timelineItem(item);
  }).join('')}</div>`;
}
function timelineView(){
  const patient=state.role==='patient'?state.patient:state.currentPatient;
  const back=state.role==='doctor'?'patient':'progress';
  const allowed=TIMELINE_FILTERS.filter(([key])=>state.role==='doctor'||key!=='clinical');
  return shell(`<div class="page-head timeline-head"><button class="back" data-view="${back}">${icon('chevron')}</button><span class="eyebrow">${state.role==='doctor'?'Карточка пациента':'Моя медкарта'}</span><h2>История наблюдения</h2><p>${esc(patient?.name||'Пациент')} · события в едином порядке</p></div>
    <div class="timeline-filters">${allowed.map(([key,label])=>`<button class="${state.timelineFilter===key?'active':''}" data-timeline-filter="${key}">${label}<span>${key==='all'?(state.timeline||[]).length:(state.timeline||[]).filter(x=>x.category===key).length}</span></button>`).join('')}</div>
    <div id="timeline-results">${timelineList(timelineEvents())}</div>
    <div class="notice notice-neutral timeline-note">${state.role==='doctor'?'Врачебные записи видны только в кабинете врача.':'Здесь показаны ваши данные и только подтверждённые врачом решения по маршрутизации.'}</div>`,
    state.role==='patient'?'progress':'home');
}
function timelinePreview(){
  const items=(state.timeline||[]).slice(0,4);
  return `<section class="section timeline-preview"><article class="card"><div class="section-head"><div><h3>Последние события</h3><p class="eyebrow">Единая история наблюдения</p></div><button class="text-btn" data-view="timeline">Вся история ${icon('chevron')}</button></div>
    ${items.length?`<div class="timeline-mini-list">${items.map(item=>{const meta=TIMELINE_META[item.type]||{icon:'activity'};return `<div class="timeline-mini tone-${esc(item.tone)}"><span>${icon(meta.icon)}</span><div><b>${esc(item.title)}</b><small>${timelineDate(item.created_at)} · ${esc(item.status)}</small></div></div>`}).join('')}</div>`:'<div class="empty compact"><p>Событий пока нет.</p></div>'}
  </article></section>`;
}

const basePatientDetailTimeline=patientDetail;
patientDetail=function(){
  let html=basePatientDetailTimeline();
  const marker='<div class="detail-grid section">';
  if(html.includes(marker))html=html.replace(marker,timelinePreview()+marker);
  return html.replace('</nav>\n  </section>','<button data-view="timeline">'+icon('clock')+' История</button></nav>\n  </section>');
}

const baseProgressTimeline=progressView;
progressView=function(){
  let html=baseProgressTimeline();
  if(state.role==='patient'){
    const card=`<section class="section timeline-entry"><button class="timeline-entry-button" data-view="timeline"><span class="row-icon">${icon('clock')}</span><span><b>Вся история наблюдения</b><small>${(state.timeline||[]).length} событий: шкалы, самоотчёты, терапия и план</small></span>${icon('chevron')}</button></section>`;
    html=html.replace('<!--/sheet-->',card+'<!--/sheet-->');
  }
  return html;
}

const baseRenderTimeline=render;
render=function(){
  if(!state.loading&&!state.error&&state.view==='timeline'){
    document.querySelector('#app').innerHTML=timelineView();bind();return;
  }
  baseRenderTimeline();
}

const baseBindTimeline=bind;
bind=function(){
  baseBindTimeline();
  document.querySelectorAll('[data-timeline-filter]').forEach(button=>button.addEventListener('click',()=>{
    state.timelineFilter=button.dataset.timelineFilter;
    document.querySelectorAll('[data-timeline-filter]').forEach(x=>x.classList.toggle('active',x===button));
    const results=document.querySelector('#timeline-results');
    if(results)results.innerHTML=timelineList(timelineEvents());
  }));
}
