// Слой компоновки: тема поверх всех стилей и вкладки в карточке пациента у врача.
// Разделы не пересоздаются и не перемещаются — только скрываются, поэтому обработчики остаются рабочими.

const themeStyles=document.querySelector('link[href="theme.css"]');
if(themeStyles)document.head.appendChild(themeStyles);

const PATIENT_TABS=[
  {id:'overview',label:'Обзор',icon:'activity'},
  {id:'clinic',label:'Клиника и план',icon:'clipboard'},
  {id:'tasks',label:'Действия',icon:'list'},
  {id:'therapy',label:'Терапия',icon:'pill'},
  {id:'ai',label:'AI и знания',icon:'sparkles'}
];

function patientPaneOf(node){
  const c=node.classList;
  if(c.contains('page-head')||c.contains('patient-workflow')||c.contains('cc-tabs'))return null;
  if(node.tagName==='SECTION'&&c.contains('card')&&c.contains('wide'))return null;
  if(c.contains('ai-summary-section')||c.contains('case-assistant-section')||node.querySelector(':scope>.kb-patient'))return 'ai';
  if(node.id==='patient-therapy'||c.contains('therapy-decision-section')||c.contains('drug-reports-section'))return 'therapy';
  if(node.id==='patient-plan'||c.contains('care-section')||c.contains('neuron-doctor-section'))return 'tasks';
  if(c.contains('clinical-section')||c.contains('detail-grid')||c.contains('history-import-section'))return 'clinic';
  return 'overview';
}

function patientTabCounts(){
  return {
    overview:(state.routingSignals||[]).filter(x=>x.status==='pending').length,
    tasks:(state.tasks||[]).filter(x=>x.status==='pending').length
  };
}

function activatePatientTab(tab,scroll){
  state.patientTab=tab;
  document.querySelectorAll('[data-cc-tab]').forEach(button=>{
    const active=button.dataset.ccTab===tab;
    button.classList.toggle('active',active);
    button.setAttribute('aria-selected',String(active));
    if(active){const bar=button.parentElement;const left=button.offsetLeft;if(left<bar.scrollLeft||left+button.offsetWidth>bar.scrollLeft+bar.clientWidth)bar.scrollLeft=left-16}
  });
  let first=true;
  document.querySelectorAll('[data-cc-pane]').forEach(node=>{
    const hidden=node.dataset.ccPane!==tab;
    node.classList.toggle('cc-pane-hidden',hidden);
    node.classList.toggle('cc-pane-first',!hidden&&first);
    if(!hidden)first=false;
  });
  if(scroll){
    const bar=document.querySelector('.cc-tabs');
    if(bar&&bar.getBoundingClientRect().top<0)window.scrollTo({top:window.scrollY+bar.getBoundingClientRect().top-80});
  }
}

function applyPatientTabs(){
  const sheet=document.querySelector('.sheet');
  const workflow=sheet?.querySelector('.patient-workflow');
  if(!sheet||!workflow)return;
  if(state.patientTabFor!==state.currentPatient.id){state.patientTabFor=state.currentPatient.id;state.patientTab='overview'}
  const used=new Set();
  [...sheet.children].forEach(node=>{const pane=patientPaneOf(node);if(pane){node.dataset.ccPane=pane;used.add(pane)}});
  const counts=patientTabCounts();
  const bar=document.createElement('nav');
  bar.className='cc-tabs';
  bar.setAttribute('role','tablist');
  bar.setAttribute('aria-label','Разделы карточки пациента');
  bar.innerHTML=PATIENT_TABS.filter(tab=>used.has(tab.id)).map(tab=>`<button class="cc-tab" role="tab" data-cc-tab="${tab.id}">${icon(tab.icon)}<span>${tab.label}</span>${counts[tab.id]?`<i>${counts[tab.id]}</i>`:''}</button>`).join('')
    +`<span class="cc-tab-spacer"></span><button class="cc-tab cc-tab-action" data-cc-proxy="progress">${icon('chart')}<span>Динамика</span></button><button class="cc-tab cc-tab-action" data-cc-proxy="messages">${icon('message')}<span>Написать</span></button>`;
  workflow.after(bar);
  sheet.classList.add('cc-tabbed');
  bar.querySelectorAll('[data-cc-tab]').forEach(button=>button.addEventListener('click',()=>activatePatientTab(button.dataset.ccTab,true)));
  bar.querySelectorAll('[data-cc-proxy]').forEach(button=>button.addEventListener('click',()=>document.querySelector(`.patient-jumpbar [data-patient-view="${button.dataset.ccProxy}"]`)?.click()));
  activatePatientTab(used.has(state.patientTab)?state.patientTab:'overview',false);
}

// Переход к скрытому разделу (кнопки «Сводка», «План», перенос рекомендаций) сначала открывает его вкладку.
const nativeScrollIntoView=Element.prototype.scrollIntoView;
Element.prototype.scrollIntoView=function(...args){
  const pane=this.closest?.('[data-cc-pane]');
  if(pane&&pane.classList.contains('cc-pane-hidden'))activatePatientTab(pane.dataset.ccPane,false);
  return nativeScrollIntoView.apply(this,args);
};

const baseBindLayout=bind;
bind=function(){
  baseBindLayout();
  if(state.role==='doctor'&&state.view==='patient'&&state.currentPatient&&!state.loading&&!state.error)applyPatientTabs();
};
