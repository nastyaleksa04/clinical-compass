state.messages=[];
state.messagesLoadedFor=null;

async function openMessages(patientId){
  state.view='messages';state.loading=true;render();
  try{
    const data=await api(`/api/patients/${patientId}/messages`);
    state.messages=data.messages||[];state.messagesLoadedFor=patientId;
    if(state.role==='patient'){
      state.unreadMessages=0;
    }else{
      const patient=state.patients.find(item=>item.id===patientId);
      if(patient){state.currentPatient=patient;patient.unread_messages=0}
    }
    state.loading=false;render();
    requestAnimationFrame(()=>{const thread=document.querySelector('.message-thread');if(thread)thread.scrollTop=thread.scrollHeight});
  }catch(error){state.loading=false;state.error=error.message;render()}
}

function messagesView(){
  if(state.role==='doctor'&&!state.currentPatient){
    return shell(`<div class="page-head"><h2>Сообщения</h2><p>Выберите пациента, чтобы открыть диалог</p></div>
    <div class="patient-list">${state.patients.map(patient=>`<button class="patient-card" data-message-patient="${patient.id}"><span class="avatar">${patient.initials}</span><span><h3>${esc(patient.name)}</h3><p>${patient.latest_message?esc(patient.latest_message):'Диалог ещё не начат'}</p></span><span>${patient.unread_messages?`<i class="message-count">${patient.unread_messages}</i>`:icon('chevron')}</span></button>`).join('')}</div>`,'messages');
  }
  const patient=state.role==='patient'?state.patient:state.currentPatient;
  const loaded=state.messagesLoadedFor===patient.id;
  const messages=loaded?state.messages:[];
  return shell(`<div class="chat-page"><div class="chat-head"><button class="back" data-chat-back>${icon('chevron')}</button><div class="avatar">${state.role==='patient'?'ЕК':patient.initials}</div><div><h2>${state.role==='patient'?'Елена Крылова':esc(patient.name)}</h2><p>${state.role==='patient'?'Лечащий врач':'Защищённый диалог с пациентом'}</p></div></div>
  <div class="notice notice-neutral chat-notice"><b>Канал не предназначен для экстренной помощи.</b> При непосредственной угрозе жизни звоните 112.</div>
  <div class="message-thread" aria-live="polite">${!loaded?'<div class="empty compact"><p>Загружаем сообщения…</p></div>':messages.length?messages.map(message=>{const own=message.sender_role===state.role;return `<div class="message-row ${own?'own':'incoming'}"><div class="message-bubble"><p>${esc(message.body)}</p><span>${fmtDate(message.created_at)}${own&&((state.role==='patient'&&message.read_by_doctor)||(state.role==='doctor'&&message.read_by_patient))?' · прочитано':''}</span></div></div>`}).join(''):'<div class="chat-empty"><span class="status-orb">'+icon('message')+'</span><h3>Начните диалог</h3><p>Сообщения сохраняются и доступны после перезапуска.</p></div>'}</div>
  <form class="message-form" id="message-form"><textarea name="body" rows="1" maxlength="4000" placeholder="Напишите сообщение" required></textarea><button class="send-button" type="submit" aria-label="Отправить">${icon('arrow')}</button></form></div>`,'messages');
}

const baseRenderMessages=render;
render=function(){
  if(!state.loading&&!state.error&&state.view==='messages'){
    document.querySelector('#app').innerHTML=messagesView();bind();return;
  }
  baseRenderMessages();
}

const baseDoctorHomeMessages=doctorHome;
doctorHome=function(){
  let html=baseDoctorHomeMessages();
  const count=state.patients.reduce((sum,p)=>sum+(p.unread_messages||0),0);
  if(!count)return html;
  const banner=`<button class="message-banner" data-view="messages"><span class="status-orb">${icon('message')}</span><span><b>${count} ${count===1?'новое сообщение':'новых сообщения'}</b><small>Открыть диалоги с пациентами</small></span>${icon('chevron')}</button>`;
  return html.replace('<div class="doctor-layout">',banner+'<div class="doctor-layout">');
}

const baseBindMessages=bind;
bind=function(){
  baseBindMessages();
  document.querySelectorAll('[data-view="messages"]').forEach(button=>button.addEventListener('click',()=>{
    const id=state.role==='patient'?state.patient?.id:state.currentPatient?.id;
    if(id)openMessages(id);
  }));
  document.querySelectorAll('[data-message-patient]').forEach(button=>button.addEventListener('click',()=>{
    const id=Number(button.dataset.messagePatient);
    state.currentPatient=state.patients.find(item=>item.id===id);
    openMessages(id);
  }));
  document.querySelector('[data-chat-back]')?.addEventListener('click',()=>{
    state.view='home';state.messagesLoadedFor=null;state.messages=[];
    if(state.role==='doctor'){state.currentPatient=null;loadState()}else render();
  });
  document.querySelector('#message-form')?.addEventListener('submit',async event=>{
    event.preventDefault();const button=event.submitter;const textarea=event.target.elements.body;
    const body=textarea.value.trim();if(!body)return;button.disabled=true;
    const patientId=state.role==='patient'?state.patient.id:state.currentPatient.id;
    try{
      await api(`/api/patients/${patientId}/messages`,{method:'POST',body:JSON.stringify({body})});
      textarea.value='';await openMessages(patientId);
    }catch(error){button.disabled=false;toast(error.message)}
  });
}

const baseLoadStateMessages=loadState;
loadState=async function(){
  await baseLoadStateMessages();
  if(state.role==='patient'&&state.patient){
    state.unreadMessages=state.unreadMessages??0;
  }
}

loadState();
