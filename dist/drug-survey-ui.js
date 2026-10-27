// Опросник скрытых побочных эффектов (app/drug_survey.py): 68 вопросов о самочувствии на фоне назначенного препарата.

state.drugSurvey={config:null,loading:false,error:'',step:0,answers:null,sending:false,result:null};
state.drugReports={key:null,items:null,loading:false};
state.drugInsights={data:null,loading:false,error:''};

function dsBlank(){return {sections:{},red_flags:{},impact:'',followups:{},note:'',share_consent:false}}

async function loadDrugSurvey(){
  const survey=state.drugSurvey;
  if(survey.loading)return;
  survey.loading=true;
  try{survey.config=await api('/api/drug-survey');survey.error=''}catch(error){survey.error=error.message}
  finally{survey.loading=false}
  render();
}
function dsConfig(){const survey=state.drugSurvey;if(!survey.config&&!survey.loading&&!survey.error)loadDrugSurvey();return survey.config}

function dsSection(id){const sections=state.drugSurvey.answers.sections;return sections[id]||(sections[id]={skipped:false,answers:{},attribution:'',onset:'',note:''})}
function dsMarked(answer){return Object.values(answer.answers).some(value=>value>0)}
function dsStepCount(config){return config.sections.length+2}
function dsAnsweredCount(config){
  const answers=state.drugSurvey.answers;
  const items=config.sections.reduce((sum,section)=>{const answer=dsSection(section.id);return sum+(answer.skipped?section.items.length:Object.keys(answer.answers).length)},0);
  return items+Object.keys(answers.red_flags).length+(answers.impact?1:0)+Object.keys(answers.followups).length;
}
function dsTotalQuestions(config){return config.sections.reduce((sum,section)=>sum+section.items.length,0)+config.red_flags.length+1+config.followups.length+1}
function dsStepValid(config,step){
  const answers=state.drugSurvey.answers;
  if(step<config.sections.length){
    const section=config.sections[step],answer=dsSection(section.id);
    if(answer.skipped)return true;
    if(section.items.some(item=>answer.answers[item.id]===undefined))return false;
    return !dsMarked(answer)||Boolean(answer.attribution&&answer.onset);
  }
  if(step===config.sections.length)return config.red_flags.every(flag=>answers.red_flags[flag.id]!==undefined);
  return Boolean(answers.impact)&&config.followups.every(item=>answers.followups[item.id]!==undefined);
}

function dsOptions(name,options,current,extra=''){
  return `<div class="ds-options">${options.map(option=>{const on=current===option.id;return `<button type="button" class="ds-option ${on?'is-on':''}" data-ds="${name}" data-value="${option.id}" ${extra} aria-pressed="${on}">${on?icon('check'):''}${esc(option.label)}</button>`}).join('')}</div>`;
}
function dsYesNo(kind,id,value){
  return `<div class="ds-yesno">${[['yes','Да',true],['no','Нет',false]].map(([key,label,flag])=>`<button type="button" class="ds-option ${value===flag?'is-on':''} ${key==='yes'&&kind==='flag'?'is-danger':''}" data-ds-yesno="${kind}" data-item="${id}" data-value="${key}" aria-pressed="${value===flag}">${esc(label)}</button>`).join('')}</div>`;
}
function dsItemText(item){return `<span class="ds-item-n">${item.n}</span><span class="ds-item-text">${esc(item.text)}${item.note?`<small>${esc(item.note)}</small>`:''}</span>`}

function drugSurveyHomeCard(){
  const config=dsConfig();
  const neuron=state.neuronKey==='patient'?state.neuron:null;
  const item=neuron?.today?.find(entry=>entry.id==='drug');
  return `<section class="ds-card ${item?.done?'is-done':''}">
    <span class="ds-card-badge">${icon('sparkles')}Главное</span>
    <div class="ds-card-top"><img src="assets/promo/aviandr.png" alt="" draggable="false"><div><span class="eyebrow">Опросник о назначенном препарате</span><h3>${esc(config?.title||'Как вам назначенный препарат?')}</h3></div></div>
    <p>Что вы замечали за последние 2 недели: сон и сны, эмоции, внимание, тело, аппетит, интимная сфера. Многое из этого люди не связывают с лечением — а врачу важно знать.</p>
    <div class="ds-card-tags">${['Сны','Эмоции','Внимание','Тело','Аппетит','+6'].map(tag=>`<span>${tag}</span>`).join('')}</div>
    <ul class="ds-card-points"><li>${icon('stethoscope')}Ответы сразу видит ваш лечащий врач</li><li>${icon('lock')}Интимную сферу можно пропустить</li><li>${icon('edit')}В каждом разделе можно написать своими словами</li></ul>
    ${item?.done?`<div class="ds-card-done">${icon('check')}<span><b>Опросник пройден</b><small>${esc(item.hint)}</small></span></div>`:''}
    <button class="btn ${item?.done?'btn-secondary':'btn-primary'}" data-ds-start>${item?.done?'Рассказать о новых изменениях':'Пройти опросник · ~10 минут'}${icon('arrow')}</button>
  </section>`;
}

function dsSectionStep(config,section,first){
  const answer=dsSection(section.id),marked=dsMarked(answer);
  return `${first?`<p class="ds-intro">${esc(config.intro)}</p>`:''}
    <div class="ds-section-head"><span class="ds-letter">${esc(section.letter)}</span><div><h3>${esc(section.title)}</h3>${section.hint?`<p class="ds-hint">${esc(section.hint)}</p>`:''}</div></div>
    ${section.sensitive?`<div class="ds-private">${icon('lock')}<span>Можно пропустить этот раздел.</span><button type="button" class="ds-option ${answer.skipped?'is-on':''}" data-ds-skip="${section.id}">${answer.skipped?icon('check'):''}Пропустить раздел</button></div>`:''}
    ${answer.skipped?'':`<div class="ds-items">
      <div class="ds-items-head"><b>${esc(config.period)}</b><button type="button" class="text-btn" data-ds-none="${section.id}">Ничего из этого</button></div>
      ${section.items.map(item=>`<div class="ds-item ${answer.answers[item.id]>0?'is-marked':''}">${dsItemText(item)}
        <div class="ds-scale">${config.scale.map(level=>`<button type="button" class="ds-level l${level.value} ${answer.answers[item.id]===level.value?'is-on':''}" data-ds-score="${item.id}" data-value="${level.value}" aria-pressed="${answer.answers[item.id]===level.value}">${esc(level.label)}</button>`).join('')}</div></div>`).join('')}
    </div>
    ${marked?`<div class="ds-followup"><div class="ds-block"><label>Если что-то отметили — как вы думаете, это связано с лечением?</label>${dsOptions('attribution',config.attribution,answer.attribution,`data-section="${section.id}"`)}</div>
      <div class="ds-block"><label>Появилось после начала лечения?</label>${dsOptions('onset',config.onset,answer.onset,`data-section="${section.id}"`)}</div></div>`:''}
    <div class="ds-block"><label for="ds-note-${section.id}">Своими словами <small>необязательно</small></label>
      <textarea id="ds-note-${section.id}" data-ds-note="${section.id}" rows="2" maxlength="1000" placeholder="Что ещё вы заметили в этом разделе? Когда началось, как меняется, что помогает">${esc(answer.note)}</textarea></div>`}`;
}

function dsFlagsStep(config){
  const answers=state.drugSurvey.answers,any=config.red_flags.some(flag=>answers.red_flags[flag.id]);
  return `<div class="ds-section-head is-danger"><span class="ds-letter">К</span><div><h3>${esc(config.red_flags_title)}</h3><p class="ds-hint">${esc(config.red_flags_hint)}</p></div></div>
    <div class="ds-items"><div class="ds-items-head"><b>Было ли у вас за последние 2 недели…</b><button type="button" class="text-btn" data-ds-flags-none>Ничего из этого не было</button></div>
      ${config.red_flags.map(flag=>`<div class="ds-item ${answers.red_flags[flag.id]?'is-danger':''}">${dsItemText(flag)}${dsYesNo('flag',flag.id,answers.red_flags[flag.id])}</div>`).join('')}</div>
    ${any?`<div class="notice notice-danger">${icon('sos')} Не ждите следующего опроса — после отправки врач сразу получит уведомление. Если это происходит прямо сейчас, звоните <a href="tel:112">112</a> или <a href="tel:103">103</a>.</div>`:''}`;
}

function dsFinalStep(config){
  const answers=state.drugSurvey.answers;
  return `<div class="ds-section-head"><span class="ds-letter">Л</span><div><h3>Как это влияет на лечение</h3></div></div>
    <div class="ds-block"><label>${esc(config.impact_question)}</label>${dsOptions('impact',config.impact,answers.impact)}</div>
    <div class="ds-items"><div class="ds-items-head"><b>За последние 2 недели…</b></div>
      ${config.followups.map(item=>`<div class="ds-item">${dsItemText(item)}${dsYesNo('followup',item.id,answers.followups[item.id])}</div>`).join('')}</div>
    <div class="ds-block"><label for="ds-note"><span class="ds-item-n">68</span> ${esc(config.final_question)}</label>
      <textarea id="ds-note" rows="4" maxlength="2000" placeholder="Например: стали сниться цветные сны, и хочется ложиться пораньше, чтобы увидеть их снова">${esc(answers.note)}</textarea></div>
    <label class="ds-consent"><input type="checkbox" id="ds-consent" ${answers.share_consent?'checked':''}><span>Разрешаю передать обезличенные ответы производителю препарата для изучения его действия</span></label>`;
}

function dsMarkedList(report){
  if(!report.sections_marked.length)return '<p class="muted">Ничего не отмечено — это тоже важный результат.</p>';
  return `<div class="ds-marked">${report.sections_marked.map(section=>`<div class="ds-marked-section">
    <header><b>${esc(section.title)}</b>${section.attribution_label?`<span class="ds-chip">Связь с лечением: ${esc(section.attribution_label)}</span>`:''}${section.onset_label?`<span class="ds-chip">${esc(section.onset==='before'?'Было и раньше':'Появилось после начала лечения')}</span>`:''}</header>
    ${section.items.map(item=>`<div class="ds-marked-item"><span>${item.n}. ${esc(item.text)}</span><em class="ds-level-pill l${item.score}">${esc(item.label)}</em></div>`).join('')}
    ${section.note?`<blockquote class="ds-note">${esc(section.note)}</blockquote>`:''}</div>`).join('')}</div>`;
}

function dsResult(){
  const result=state.drugSurvey.result;
  const urgent=result.signals.includes('mandatory'),recommended=result.signals.includes('recommended');
  const mood=state.neuronKey==='patient'&&state.neuron?state.neuron.mood:'blooming';
  return `<section class="ds-result">${neuronImg(mood,'ds-result-img')}<span class="eyebrow">Опросник отправлен</span><h2>Спасибо!</h2>
      <p>Ответы получил ваш лечащий врач. ${result.share_consent?'Обезличенные данные помогут лучше понять действие препарата.':''}</p></section>
    ${urgent?`<div class="notice notice-danger">${icon('sos')} Вы отметили признак, о котором нужно срочно сообщить. Врач получил уведомление. Если состояние угрожает жизни — звоните <a href="tel:112">112</a> или <a href="tel:103">103</a>.</div>`:recommended?`<div class="notice notice-warn">${icon('info')} Врач увидит, что это вас беспокоит, и свяжется при необходимости. Не меняйте дозу и не прекращайте приём самостоятельно.</div>`:''}
    <section class="card"><div class="section-head"><div><p class="eyebrow">Отмечено пунктов: ${result.marked_count}${result.impact_label?` · ${esc(result.impact_label)}`:''}</p><h2>Что вы отметили</h2></div></div>
      ${dsMarkedList(result)}${result.note?`<blockquote class="ds-note">${esc(result.note)}</blockquote>`:''}</section>
    <section class="ds-next card"><span>${icon('heart')}</span><div><b>Следующий шаг — самочувствие</b><small>Отметьте настроение, тревогу и сон за сегодня</small></div><button class="btn btn-primary" data-view="report">Отметить</button></section>
    <button class="btn btn-secondary ds-home" data-view="home">На главную</button>`;
}

function drugSurveyView(){
  const survey=state.drugSurvey,config=dsConfig();
  const head=`<div class="page-head ds-head"><button class="back" data-view="home">${icon('chevron')}</button><div class="neuron-titled">${neuronImg('calm','neuron-avatar is-large')}<div><span class="eyebrow">Нейрон спрашивает</span><h2>Как вам назначенный препарат?</h2><p>Опросник скрытых побочных эффектов</p></div></div></div>`;
  if(!config)return shell(head+`<article class="card">${survey.error?esc(survey.error):'Загружаем опросник…'}</article>`,'home');
  if(survey.result)return shell(head+dsResult(),'home');
  if(!survey.answers)survey.answers=dsBlank();
  const total=dsStepCount(config),step=Math.min(survey.step,total-1);
  const body=step<config.sections.length?dsSectionStep(config,config.sections[step],step===0):step===config.sections.length?dsFlagsStep(config):dsFinalStep(config);
  const last=step===total-1,valid=dsStepValid(config,step);
  const answered=Math.min(dsAnsweredCount(config),dsTotalQuestions(config));
  return shell(`${head}<div class="ds-progress"><div><i style="width:${Math.round((step+1)/total*100)}%"></i></div><span>Раздел ${step+1} из ${total} · ответов ${answered} из ${dsTotalQuestions(config)}</span></div>
    <section class="card ds-step">${body}
      ${survey.error?`<div class="notice notice-danger">${icon('warning')} ${esc(survey.error)}</div>`:''}
      <div class="ds-nav">${step?`<button class="btn btn-secondary" data-ds-nav="-1">${icon('chevron')}Назад</button>`:'<span></span>'}
      <button class="btn btn-primary" ${last?'data-ds-submit':'data-ds-nav="1"'} ${!valid||survey.sending?'disabled':''}>${last?(survey.sending?'Отправляем…':'Отправить врачу'):'Далее'}</button></div></section>`,'home');
}

async function submitDrugSurvey(){
  const survey=state.drugSurvey,config=survey.config,answers=survey.answers;
  survey.sending=true;survey.error='';render();
  const payload={drug_id:config.drug.id,
    sections:config.sections.map(section=>{const answer=dsSection(section.id),marked=dsMarked(answer);return {section:section.id,skipped:answer.skipped,answers:answer.skipped?{}:answer.answers,attribution:!answer.skipped&&marked?answer.attribution:null,onset:!answer.skipped&&marked?answer.onset:null,note:answer.skipped?'':answer.note}}),
    red_flags:answers.red_flags,impact:answers.impact,followups:answers.followups,note:answers.note,share_consent:answers.share_consent};
  try{survey.result=await api(`/api/patients/${state.patient.id}/drug-reports`,{method:'POST',body:JSON.stringify(payload)});survey.answers=null;survey.step=0;state.drugReports.key=null;window.scrollTo(0,0)}
  catch(error){survey.error=error.message}
  finally{survey.sending=false;render()}
}

function bindDrugSurvey(){
  const survey=state.drugSurvey;
  document.querySelectorAll('[data-ds-start]').forEach(button=>button.addEventListener('click',()=>{survey.result=null;survey.answers=dsBlank();survey.step=0;survey.error='';state.view='drug-survey';render();window.scrollTo(0,0)}));
  if(state.view!=='drug-survey'||!survey.answers)return;
  const config=survey.config,answers=survey.answers;
  const section=survey.step<config.sections.length?config.sections[survey.step]:null;
  const keepScroll=fn=>{const y=window.scrollY;fn();render();window.scrollTo(0,y)};
  document.querySelectorAll('[data-ds-score]').forEach(button=>button.addEventListener('click',()=>keepScroll(()=>{dsSection(section.id).answers[button.dataset.dsScore]=Number(button.dataset.value)})));
  document.querySelectorAll('[data-ds-none]').forEach(button=>button.addEventListener('click',()=>keepScroll(()=>{const answer=dsSection(section.id);section.items.forEach(item=>{answer.answers[item.id]=0})})));
  document.querySelectorAll('[data-ds-skip]').forEach(button=>button.addEventListener('click',()=>keepScroll(()=>{const answer=dsSection(button.dataset.dsSkip);answer.skipped=!answer.skipped})));
  document.querySelectorAll('[data-ds]').forEach(button=>button.addEventListener('click',()=>keepScroll(()=>{
    const kind=button.dataset.ds,value=button.dataset.value;
    if(kind==='attribution'||kind==='onset')dsSection(button.dataset.section)[kind]=value;
    else answers[kind]=value;
  })));
  document.querySelectorAll('[data-ds-yesno]').forEach(button=>button.addEventListener('click',()=>keepScroll(()=>{
    const target=button.dataset.dsYesno==='flag'?answers.red_flags:answers.followups;
    target[button.dataset.item]=button.dataset.value==='yes';
  })));
  document.querySelector('[data-ds-flags-none]')?.addEventListener('click',()=>keepScroll(()=>{config.red_flags.forEach(flag=>{answers.red_flags[flag.id]=false})}));
  document.querySelectorAll('[data-ds-note]').forEach(input=>input.addEventListener('input',()=>{dsSection(input.dataset.dsNote).note=input.value}));
  document.querySelector('#ds-note')?.addEventListener('input',event=>{answers.note=event.target.value});
  document.querySelector('#ds-consent')?.addEventListener('change',event=>{answers.share_consent=event.target.checked});
  document.querySelectorAll('[data-ds-nav]').forEach(button=>button.addEventListener('click',()=>{survey.step=Math.max(0,survey.step+Number(button.dataset.dsNav));survey.error='';render();window.scrollTo(0,0)}));
  document.querySelector('[data-ds-submit]')?.addEventListener('click',submitDrugSurvey);
}

// ---------- врач ----------

async function loadDrugReports(id){
  const reports=state.drugReports;
  reports.loading=true;
  try{reports.items=await api(`/api/patients/${id}/drug-reports`)}catch{reports.items=[]}
  finally{reports.key=id;reports.loading=false;render()}
}

function drugReportsSection(){
  const id=state.currentPatient?.id,reports=state.drugReports;
  if(reports.key!==id&&!reports.loading)loadDrugReports(id);
  const items=reports.key===id?reports.items||[]:null;
  const head=`<div class="section-head"><div><p class="eyebrow">Пострегистрационное наблюдение</p><h2>Опросники побочных эффектов</h2></div><button class="text-btn" data-view="drug-insights">Сводка по препарату ${icon('chevron')}</button></div>`;
  if(!items)return `<section class="card drug-reports-section">${head}<p class="muted">Загружаем…</p></section>`;
  if(!items.length)return `<section class="card drug-reports-section">${head}<p class="muted">Пациент ещё не заполнял опросник.</p></section>`;
  const date=value=>new Intl.DateTimeFormat('ru-RU',{day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'}).format(new Date(value));
  return `<section class="card drug-reports-section">${head}<div class="ds-reports">${items.slice(0,4).map(item=>`<article class="ds-report ${item.red_flags.length?'is-danger':''}">
    <header><b>${date(item.created_at)}</b><span>Отмечено пунктов: ${item.marked_count}${item.strong_count?` · заметно или сильно: ${item.strong_count}`:''}${item.impact_label?` · мешает жить: ${esc(item.impact_label.toLowerCase())}`:''}</span>${item.share_consent?'<em class="badge badge-new">Согласие на передачу</em>':''}</header>
    ${item.red_flag_labels.length?`<div class="notice notice-danger">${icon('warning')} Срочно: ${item.red_flag_labels.map(esc).join('; ')}</div>`:''}
    ${item.followup_labels.length?`<div class="ds-followup-flags">${item.followup_labels.map(text=>`<span>${icon('info')}${esc(text)}</span>`).join('')}</div>`:''}
    ${dsMarkedList(item)}
    ${item.note?`<blockquote class="ds-note"><b>Что-то ещё:</b> ${esc(item.note)}</blockquote>`:''}
    ${item.skipped.length?`<footer>Пропущено: ${item.skipped.map(esc).join(', ')}</footer>`:''}
  </article>`).join('')}</div></section>`;
}

async function loadDrugInsights(){
  const insights=state.drugInsights;
  insights.loading=true;
  try{insights.data=await api('/api/drug-insights');insights.error=''}catch(error){insights.error=error.message}
  finally{insights.loading=false;render()}
}

function drugInsightsView(){
  const insights=state.drugInsights;
  if(!insights.data&&!insights.loading&&!insights.error)loadDrugInsights();
  const data=insights.data;
  const head=`<div class="page-head"><button class="back" data-view="home">${icon('chevron')}</button><div><span class="eyebrow">Пострегистрационное наблюдение</span><h2>${data?esc(data.drug.name):'Препарат'} · что замечают пациенты</h2><p>Обезличенная сводка опросников скрытых побочных эффектов по всем вашим пациентам</p></div></div>`;
  if(!data)return shell(head+`<article class="card">${insights.error?esc(insights.error):'Загружаем…'}</article>`,'home');
  const max=Math.max(1,...data.top_items.map(item=>item.count));
  const pct=(part,whole)=>whole?Math.round(part/whole*100):0;
  return shell(`${head}
    <div class="ds-stats"><div><b>${data.reports}</b><span>опросников</span></div><div><b>${data.patients}</b><span>пациентов</span></div><div><b>${data.consented}</b><span>с согласием на передачу</span></div><div class="${data.red_flags?'is-alert':''}"><b>${data.red_flags}</b><span>с признаками для срочной связи</span></div><div class="${data.thinking_stop?'is-alert':''}"><b>${data.thinking_stop}</b><span>думали прекратить лечение</span></div></div>
    <section class="card"><div class="section-head"><div><p class="eyebrow">Чаще всего</p><h2>Отмеченные пункты</h2></div></div>
      ${data.top_items.length?`<div class="ds-bars">${data.top_items.map(item=>`<div class="ds-bar"><span><em>${esc(item.section)}·${item.n}</em> ${esc(item.text)}</span><div><i style="width:${item.count/max*100}%"></i>${item.strong?`<i class="strong" style="width:${item.strong/max*100}%"></i>`:''}</div><b>${item.count}</b></div>`).join('')}</div>
      <div class="ds-legend"><span><i class="other"></i>Отмечено</span><span><i class="bother"></i>Из них заметно или сильно</span></div>`:'<p class="muted">Пока ничего не отмечено.</p>'}</section>
    <section class="card"><div class="section-head"><div><p class="eyebrow">По разделам</p><h2>Доля опросников с отмеченными пунктами</h2></div></div>
      <div class="ds-domains">${data.sections.map(section=>{const levels=section.mild+section.marked+section.strong;return `<div class="ds-domain"><header><b>${esc(section.title)}</b><span>${pct(section.with_symptoms,section.answered)}%</span></header>
        <div class="ds-split">${levels?`<i class="mild" style="width:${pct(section.mild,levels)}%"></i><i class="other" style="width:${pct(section.marked,levels)}%"></i><i class="bother" style="width:${pct(section.strong,levels)}%"></i>`:''}</div>
        <small>${section.with_symptoms} из ${section.answered} · связывают с лечением ${section.attributed} · впервые после начала ${section.new_onset}</small></div>`}).join('')}</div>
      <div class="ds-legend"><span><i class="mild"></i>Немного</span><span><i class="other"></i>Заметно</span><span><i class="bother"></i>Сильно</span></div></section>
    ${data.notes.length?`<section class="card"><div class="section-head"><div><p class="eyebrow">Своими словами</p><h2>Что пишут пациенты</h2></div></div><div class="ds-quotes">${data.notes.map(note=>`<blockquote class="ds-note"><b>${esc(note.section)}:</b> ${esc(note.text)}</blockquote>`).join('')}</div></section>`:''}
    <div class="notice notice-neutral">${icon('info')} Серьёзные и непредвиденные нежелательные реакции врач сообщает в Росздравнадзор (АИС «Фармаконадзор»). Производителю передаются только опросники с согласием пациента.</div>`,'home');
}

const baseDoctorHomeDrug=doctorHome;
doctorHome=function(){
  const html=baseDoctorHomeDrug();
  const banner=`<button class="ds-doctor-banner" data-view="drug-insights"><img src="assets/promo/aviandr.png" alt="" draggable="false"><span><span class="eyebrow">Пострегистрационное наблюдение</span><b>Назначенные препараты: что замечают пациенты</b><small>Опросник скрытых побочных эффектов: сон и сны, эмоции, внимание, тело, интимная сфера</small></span>${icon('chevron')}</button>`;
  return html.replace('<div class="doctor-stats">',banner+'<div class="doctor-stats">');
};

const basePatientDetailDrug=patientDetail;
patientDetail=function(){
  const html=basePatientDetailDrug();
  return html.includes('<!--/sheet-->')?html.replace('<!--/sheet-->',drugReportsSection()+'<!--/sheet-->'):html;
};

const baseRenderDrug=render;
render=function(){
  if(!state.loading&&!state.error&&state.role==='patient'&&state.view==='drug-survey'){document.querySelector('#app').innerHTML=drugSurveyView();bind();return}
  if(!state.loading&&!state.error&&state.role==='doctor'&&state.view==='drug-insights'){document.querySelector('#app').innerHTML=drugInsightsView();bind();return}
  baseRenderDrug();
};

const baseBindDrug=bind;
bind=function(){baseBindDrug();bindDrugSurvey()};
