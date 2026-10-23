state.profile=null;
state.currentProfile=null;
state.alerting=null;

const PROFILE_FIELDS=['phone','email','emergency_name','emergency_phone','reminder_enabled','reminder_time','notify_messages','notify_plan'];

function medcardNumber(id){return 'КК-'+String(id||0).padStart(6,'0')}
function fmtDay(value){return value?new Intl.DateTimeFormat('ru-RU',{day:'numeric',month:'long',year:'numeric'}).format(new Date(value)):'—'}
function plural(n,one,few,many){const m10=n%10,m100=n%100;return m10===1&&m100!==11?one:m10>=2&&m10<=4&&(m100<12||m100>14)?few:many}

function listRow({glyph,title,sub='',end='',view='',href='',attrs='',tone=''}){
  const inner=`<span class="row-icon ${tone}">${icon(glyph)}</span><span class="row-text"><b>${title}</b>${sub?`<small>${sub}</small>`:''}</span><span class="row-end">${end}${icon('chevron')}</span>`;
  if(href)return `<a class="list-row" href="${href}" ${attrs}>${inner}</a>`;
  return `<button class="list-row" ${view?`data-view="${view}"`:''} ${attrs}>${inner}</button>`;
}
function toggleRow({glyph,title,sub,flag,checked,extra=''}){
  return `<label class="list-row toggle-row"><span class="row-icon">${icon(glyph)}</span><span class="row-text"><b>${title}</b><small>${sub}</small>${extra}</span><input class="switch" type="checkbox" data-profile-flag="${flag}" ${checked?'checked':''} aria-label="${title}"></label>`;
}
function rowGroup(title,rows){return `<section class="row-group">${title?`<h3>${title}</h3>`:''}<div class="row-card">${rows.join('')}</div></section>`}
function countBadge(n){return n?`<i class="row-badge">${n}</i>`:''}

function patientProfileView(){
  const patient=state.patient||{};const profile=state.profile||{};
  const pending=(state.tasks||[]).filter(task=>task.status==='pending').length;
  const unread=state.unreadMessages||0;
  const lastAssessment=state.assessments[0];
  const adherence=state.adherence||{};
  return shell(`<div class="page-head profile-head"><h2>Профиль</h2></div>
  <button class="profile-card" data-view="profile-edit"><span class="avatar avatar-round avatar-xl">${esc(patient.initials?.[0]||'А')}<i class="verified">${icon('check')}</i></span><span><b>${esc(patient.name||'Пациент')}</b><small>Медкарта ${medcardNumber(patient.id)}</small></span>${icon('chevron')}</button>
  <div class="profile-stats"><div><b>${patient.age??'—'}</b><span>${plural(patient.age||0,'год','года','лет')}</span></div><div><b>${adherence.percent!=null?adherence.percent+'%':'—'}</b><span>приверженность</span></div><div><b>${state.assessments.length}</b><span>${plural(state.assessments.length,'опросник','опросника','опросников')}</span></div></div>
  ${rowGroup('Моё лечение',[
    listRow({glyph:'stethoscope',title:'Лечащий врач',sub:'Елена Крылова · на связи',end:countBadge(unread),view:'messages'}),
    listRow({glyph:'list',title:'Мой план',sub:pending?`${pending} ${plural(pending,'действие','действия','действий')} к выполнению`:'Все действия выполнены',end:countBadge(pending),view:'plan'}),
    listRow({glyph:'clipboard',title:'Опросники',sub:lastAssessment?`Последний: ${fmtDate(lastAssessment.created_at)}`:'PHQ-9 и GAD-7',view:'assessments'}),
    listRow({glyph:'activity',title:'Динамика состояния',sub:'Графики и ежедневные отметки',view:'progress'}),
  ])}
  ${rowGroup('Контакты',[
    listRow({glyph:'phone',title:'Телефон',sub:esc(profile.phone||'Не указан'),view:'profile-edit'}),
    listRow({glyph:'mail',title:'Электронная почта',sub:esc(profile.email||'Не указана'),view:'profile-edit'}),
    listRow({glyph:'users',title:'Контакт для экстренной связи',sub:profile.emergency_name?`${esc(profile.emergency_name)} · ${esc(profile.emergency_phone||'без телефона')}`:'Не указан',view:'profile-edit'}),
  ])}
  ${rowGroup('Уведомления',[
    toggleRow({glyph:'clock',title:'Напоминание о самоотчёте',sub:profile.reminder_enabled?'Ежедневно в выбранное время':'Выключено',flag:'reminder_enabled',checked:profile.reminder_enabled,extra:profile.reminder_enabled?`<input class="time-chip" type="time" data-profile-time value="${esc(profile.reminder_time||'20:00')}" aria-label="Время напоминания">`:''}),
    toggleRow({glyph:'message',title:'Сообщения врача',sub:'Сообщать о новых ответах',flag:'notify_messages',checked:profile.notify_messages}),
    toggleRow({glyph:'file',title:'Изменения плана',sub:'Новые действия и подтверждения',flag:'notify_plan',checked:profile.notify_plan}),
  ])}
  ${rowGroup('Безопасность и данные',[
    listRow({glyph:'shield',title:'Согласие на обработку данных',sub:profile.consent_accepted_at?`Подписано ${fmtDay(profile.consent_accepted_at)}`:'Не подписано',end:profile.consent_accepted_at?'<i class="row-ok">'+icon('check')+'</i>':'',attrs:'data-consent'}),
    listRow({glyph:'lock',title:'Доступ к медкарте',sub:'Данные видит только лечащий врач',attrs:'data-access-info'}),
    listRow({glyph:'phone',title:'Экстренная помощь — 112',sub:'При непосредственной угрозе жизни',href:'tel:112',tone:'row-icon-danger'}),
  ])}
  ${rowGroup('Демо-режим',[
    listRow({glyph:'switch',title:'Открыть кабинет врача',sub:'Переключатель ролей заменяет авторизацию в прототипе',attrs:'data-role-toggle'}),
  ])}
  <p class="profile-foot">Клинический компас · прототип 0.10<br>Все имена и медицинские данные синтетические.</p>`,'profile');
}

function profileEditView(){
  const p=state.profile||{};
  return shell(`<div class="page-head"><button class="back" data-view="profile">${icon('chevron')}</button><h2>Личные данные</h2><p>Контакты помогают врачу связаться с вами</p></div>
  <form class="form-card" id="profile-form" novalidate>
    <div class="field"><label>ФИО</label><input class="text-input" value="${esc(state.patient?.name||'')}" disabled><small class="field-note">Изменяется в регистратуре клиники</small></div>
    <div class="form-grid"><div class="field"><label for="pf-phone">Телефон</label><input class="text-input" id="pf-phone" name="phone" type="tel" inputmode="tel" maxlength="30" value="${esc(p.phone||'')}" placeholder="+7 900 000-00-00"></div>
    <div class="field"><label for="pf-email">Электронная почта</label><input class="text-input" id="pf-email" name="email" type="email" maxlength="120" value="${esc(p.email||'')}" placeholder="name@example.com"></div></div>
    <h4 class="form-subhead">Контакт для экстренной связи</h4>
    <div class="form-grid"><div class="field"><label for="pf-ename">Имя</label><input class="text-input" id="pf-ename" name="emergency_name" maxlength="120" value="${esc(p.emergency_name||'')}" placeholder="Кто это"></div>
    <div class="field"><label for="pf-ephone">Телефон</label><input class="text-input" id="pf-ephone" name="emergency_phone" type="tel" inputmode="tel" maxlength="30" value="${esc(p.emergency_phone||'')}"></div></div>
    <div class="notice notice-neutral">Врач может использовать экстренный контакт только при угрозе вашей безопасности.</div>
    <button class="btn btn-primary btn-wide" type="submit" style="margin-top:20px">${icon('check')} Сохранить</button>
  </form>`,'profile');
}

function doctorProfileView(){
  const patients=state.patients||[];
  const alerts=(state.alerts||[]).filter(alert=>alert.status!=='acknowledged');
  const unread=patients.reduce((sum,p)=>sum+(p.unread_messages||0),0);
  const pending=patients.reduce((sum,p)=>sum+(p.pending_signals||0),0);
  const acknowledged=(state.alerts||[]).filter(alert=>alert.response_seconds!=null);
  const avgResponse=acknowledged.length?Math.round(acknowledged.reduce((sum,a)=>sum+a.response_seconds,0)/acknowledged.length):null;
  const settings=state.alerting||{};
  const minutes=settings.escalation_seconds?Math.round(settings.escalation_seconds/60):15;
  return shell(`<div class="page-head profile-head"><h2>Профиль</h2></div>
  <div class="profile-card"><span class="avatar avatar-round avatar-xl">ЕК<i class="verified">${icon('check')}</i></span><span><b>Елена Крылова</b><small>Лечащий врач · кабинет врача</small></span></div>
  <div class="profile-stats"><div><b>${patients.length}</b><span>${plural(patients.length,'пациент','пациента','пациентов')}</span></div><div class="${alerts.length?'is-alert':''}"><b>${alerts.length}</b><span>активных алертов</span></div><div><b>${avgResponse==null?'—':avgResponse<60?avgResponse+' с':Math.round(avgResponse/60)+' мин'}</b><span>средняя реакция</span></div></div>
  ${rowGroup('Работа',[
    listRow({glyph:'users',title:'Мои пациенты',sub:`${patients.length} в наблюдении`,view:'home'}),
    listRow({glyph:'message',title:'Сообщения',sub:unread?`${unread} ${plural(unread,'непрочитанное','непрочитанных','непрочитанных')}`:'Новых сообщений нет',end:countBadge(unread),view:'messages'}),
    listRow({glyph:'warning',title:'Сигналы маршрутизации',sub:pending?`${pending} ожидают решения`:'Все сигналы обработаны',end:countBadge(pending),view:'home'}),
  ])}
  ${rowGroup('Критический алертинг',[
    listRow({glyph:'clock',title:'Эскалация дежурному врачу',sub:`Если нет реакции ${minutes} мин`,attrs:'data-kb-open="alerting"'}),
    listRow({glyph:'bell',title:'Действия системы',sub:esc((settings.doctor_actions||['Создать критический алерт']).join(' · ')),attrs:'data-kb-open="alerting"'}),
  ])}
  ${rowGroup('База знаний',[
    listRow({glyph:'book',title:'Все материалы',sub:'Шкалы, терапия, протоколы и ваши статьи',view:'knowledge'}),
    listRow({glyph:'clipboard',title:'Опросники',sub:esc((state.scales||[]).map(scale=>scale.name).join(', ')||'PHQ-9, GAD-7'),attrs:'data-kb-open="phq9"'}),
    listRow({glyph:'pill',title:'Справочник терапии',sub:'АВИАНДР® · показания и противопоказания',attrs:'data-kb-open="aviandr"'}),
  ])}
  ${rowGroup('Демо-режим',[
    listRow({glyph:'switch',title:'Открыть кабинет пациента',sub:'Переключатель ролей заменяет авторизацию в прототипе',attrs:'data-role-toggle'}),
  ])}
  <p class="profile-foot">Клинический компас · прототип 0.10<br>Система формирует сигналы, решения принимает врач.</p>`,'profile');
}

function profilePayload(changes={}){
  const current=state.profile||{};
  return Object.fromEntries(PROFILE_FIELDS.map(key=>[key,key in changes?changes[key]:current[key]]));
}
async function saveProfile(changes,message){
  state.profile=await api('/api/profile',{method:'PUT',body:JSON.stringify(profilePayload(changes))});
  render();toast(message);
}

const baseRenderProfile=render;
render=function(){
  if(!state.loading&&!state.error&&['profile','profile-edit'].includes(state.view)){
    document.querySelector('#app').innerHTML=state.role==='doctor'?doctorProfileView():state.view==='profile-edit'?profileEditView():patientProfileView();
    bind();return;
  }
  baseRenderProfile();
}

const basePatientDetailProfile=patientDetail;
patientDetail=function(){
  const html=basePatientDetailProfile();
  const p=state.currentProfile;
  if(!p||(!p.phone&&!p.emergency_name))return html;
  const phone=p.phone?`<a class="chip chip-contact" href="tel:${esc(p.phone.replace(/[^0-9+]/g,''))}">${icon('phone')} Пациент: ${esc(p.phone)}</a>`:'';
  const emergency=p.emergency_name?`<span class="chip chip-contact">${icon('users')} Экстренный контакт: ${esc(p.emergency_name)}${p.emergency_phone?' · '+esc(p.emergency_phone):''}</span>`:'';
  return html.replace('<span class="chip">Данные синтетические</span>',`${phone}${emergency}<span class="chip">Данные синтетические</span>`);
}

const baseBindProfile=bind;
bind=function(){
  baseBindProfile();
  document.querySelectorAll('[data-role-toggle]').forEach(button=>button.addEventListener('click',()=>document.querySelector('#role-switch')?.click()));
  document.querySelectorAll('[data-profile-flag]').forEach(input=>input.addEventListener('change',async()=>{
    input.disabled=true;
    try{await saveProfile({[input.dataset.profileFlag]:input.checked},input.checked?'Уведомление включено':'Уведомление выключено')}
    catch(error){input.checked=!input.checked;input.disabled=false;toast(error.message)}
  }));
  const time=document.querySelector('[data-profile-time]');
  time?.addEventListener('change',async()=>{
    if(!time.value)return;
    try{await saveProfile({reminder_time:time.value},`Напоминание в ${time.value}`)}catch(error){toast(error.message)}
  });
  document.querySelector('[data-consent]')?.addEventListener('click',()=>toast(state.profile?.consent_accepted_at?'Согласие действует. Отозвать его можно в клинике':'Согласие не подписано'));
  document.querySelector('[data-access-info]')?.addEventListener('click',()=>toast('Доступ к данным есть только у лечащего врача'));
  document.querySelector('#profile-form')?.addEventListener('submit',async event=>{
    event.preventDefault();const form=event.target;const button=event.submitter;
    const data=Object.fromEntries(['phone','email','emergency_name','emergency_phone'].map(key=>[key,form.elements[key].value.trim()]));
    if(data.email&&!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(data.email)){toast('Проверьте адрес электронной почты');form.elements.email.focus();return}
    if([data.phone,data.emergency_phone].some(value=>value&&!/^[0-9+()\- ]+$/.test(value))){toast('Телефон может содержать только цифры, пробелы, +, - и скобки');return}
    button.disabled=true;
    try{state.profile=await api('/api/profile',{method:'PUT',body:JSON.stringify(profilePayload(data))});state.view='profile';render();scrollTo(0,0);toast('Личные данные сохранены')}
    catch(error){button.disabled=false;toast(error.message)}
  });
}
