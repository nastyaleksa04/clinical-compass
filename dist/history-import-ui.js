// Импорт истории болезни (app/history_import.py): разбор текста или PDF в черновик для врача.

state.historyImport={patientId:null,text:'',filename:'',file:null,loading:false,error:'',result:null,selected:{}};

const HI_FIELDS=[
  ['visit_reason','Причина обращения'],['complaints','Жалобы'],['symptom_duration','Длительность симптомов'],['history','Анамнез'],
  ['comorbidities','Сопутствующие заболевания'],['current_medications','Текущие препараты'],['allergies','Аллергии'],['working_hypothesis','Рабочая гипотеза / диагноз'],
];
const HI_FACTORS={pregnancy:'Беременность',breastfeeding:'Грудное вскармливание',epilepsy_or_brain_disease:'Эпилепсия / органическое поражение мозга',egfr_below_60:'СКФ < 60',
  hepatic_impairment:'Печёночная недостаточность',maoi_recent:'ИМАО ≤ 2 недель',lactose_disorder:'Нарушение усвоения лактозы',serotonergic_drugs:'Серотонинергические препараты',
  cyp2d6_inhibitors:'Ингибиторы CYP2D6',sedatives:'Седативные препараты',alcohol:'Алкоголь',driving:'Управление транспортом'};
const HI_PREGNANCY={yes:'Беременна',no:'Не беременна',not_applicable:'Неприменимо',unknown:'Не указано'};

function hiState(){
  const item=state.historyImport,id=state.currentPatient?.id;
  if(item.patientId!==id)Object.assign(item,{patientId:id,text:'',filename:'',file:null,loading:false,error:'',result:null,selected:{}});
  return item;
}

function hiResultView(result){
  const item=state.historyImport,fields=result.fields;
  const chips=[result.age?`${result.age} лет`:'',result.sex==='female'?'женский пол':result.sex==='male'?'мужской пол':'',...result.icd_codes,
    ...Object.entries(result.scales).map(([key,value])=>`${key==='phq9'?'PHQ-9':'GAD-7'}: ${value}`)].filter(Boolean);
  const flags=[
    fields.self_harm_concern?['danger','Риск самоповреждения',result.evidence.self_harm_concern]:null,
    fields.psychosis_signs?['danger','Психотические признаки',result.evidence.psychosis_signs]:null,
    ['neutral',`Беременность: ${HI_PREGNANCY[fields.pregnancy_status]}`,result.evidence.pregnancy_status],
  ].filter(Boolean);
  const factors=Object.entries(result.therapy_factors).filter(([,value])=>value);
  return `<div class="hi-result">
    <div class="hi-meta"><span>${icon('check')} Разобрано за ${result.elapsed_ms} мс · ${esc(result.source)}</span><span>Разделы: ${result.sections_found.length?result.sections_found.length:'не найдены, разбор по всему тексту'}</span></div>
    ${chips.length?`<div class="hi-chips">${chips.map(chip=>`<span>${esc(chip)}</span>`).join('')}</div>`:''}
    ${result.warnings.map(text=>`<div class="notice ${/суицид|самоповр/.test(text)?'notice-danger':'notice-warn'}">${icon('warning')} ${esc(text)}</div>`).join('')}
    <div class="hi-flags">${flags.map(([tone,label,evidence])=>`<div class="hi-flag tone-${tone}"><b>${esc(label)}</b>${evidence?`<small>«${esc(evidence)}»</small>`:''}</div>`).join('')}</div>
    <h3>Поля клинической сводки</h3>
    <div class="hi-fields">${HI_FIELDS.filter(([key])=>fields[key]).map(([key,label])=>`<label class="hi-field"><input type="checkbox" data-hi-field="${key}" ${item.selected[key]!==false?'checked':''}><span><b>${label}</b><small>${esc(fields[key])}</small></span></label>`).join('')||'<p class="muted">Текстовые поля не найдены.</p>'}</div>
    ${result.medications.length?`<h3>Препараты</h3><div class="hi-meds">${result.medications.map(med=>`<span class="${med.status==='stopped'?'is-stopped':''}"><b>${esc(med.name)}</b>${med.dose?` ${esc(med.dose)}`:''}${med.schedule?` · ${esc(med.schedule)}`:''}${med.status==='stopped'?' · отменён':''}</span>`).join('')}</div>`:''}
    <h3>Факторы для чек-листа Авиандра</h3>
    ${factors.length?`<div class="hi-factors">${factors.map(([key])=>`<span title="${esc(result.evidence[key]||'')}">${icon('warning')}${esc(HI_FACTORS[key]||key)}</span>`).join('')}</div>`:'<p class="muted">Факторов риска из чек-листа не найдено.</p>'}
    <div class="hi-actions"><button class="btn btn-primary" data-hi-apply>${icon('check')} Перенести отмеченное в клиническую сводку</button>${factors.length?`<button class="btn btn-secondary" data-hi-factors>${icon('pill')} Отметить факторы в чек-листе терапии</button>`:''}</div>
    <p class="hi-note">${icon('shield')} Это черновик: ничего не сохраняется без вашего подтверждения. Флаги риска при переносе только добавляются и никогда не снимаются.</p>
  </div>`;
}

function historyImportSection(){
  const item=hiState();
  return `<section class="card history-import-section"><div class="section-head"><div><p class="eyebrow">Извлечение сведений</p><h2>Импорт истории болезни</h2></div><span class="badge badge-new">TXT · PDF</span></div>
    <p class="hi-intro">Вставьте текст выписки, направления или осмотра либо загрузите файл. Разделы распознаются в любом порядке и оформлении: «Жалобы:», «Ds:», «An. morbi», заголовки капсом, SOAP.</p>
    <div class="hi-input"><textarea id="hi-text" rows="5" maxlength="200000" placeholder="Например: Жалобы: тревога, бессонница. Ds: F41.1. Принимает сертралин 50 мг…">${esc(item.text)}</textarea>
      <div class="hi-row"><label class="hi-file">${icon('file')}<span>${item.file?esc(item.filename):'Выбрать файл .txt или .pdf'}</span><input type="file" id="hi-file" accept=".txt,.pdf,text/plain,application/pdf"></label>
      <button class="btn btn-primary" data-hi-run ${item.loading?'disabled':''}>${item.loading?'Разбираем…':`${icon('sparkles')} Извлечь сведения`}</button></div></div>
    ${item.error?`<div class="notice notice-danger">${icon('warning')} ${esc(item.error)}</div>`:''}
    ${item.result?hiResultView(item.result):''}
  </section>`;
}

async function runHistoryImport(){
  const item=state.historyImport;
  if(!item.file&&!item.text.trim()){item.error='Вставьте текст или выберите файл';render();return}
  item.loading=true;item.error='';render();
  try{
    let body={text:item.text};
    if(item.file){
      const buffer=new Uint8Array(await item.file.arrayBuffer());
      let binary='';for(let index=0;index<buffer.length;index+=0x8000)binary+=String.fromCharCode(...buffer.subarray(index,index+0x8000));
      body={filename:item.filename,content_base64:btoa(binary)};
    }
    item.result=await api(`/api/patients/${item.patientId}/history-import`,{method:'POST',body:JSON.stringify(body)});
    item.selected={};
  }catch(error){item.error=error.message}
  finally{item.loading=false;render()}
}

async function applyHistoryImport(){
  const item=state.historyImport,fields=item.result.fields,current=state.clinicalProfile||{};
  const payload={};
  HI_FIELDS.forEach(([key])=>{payload[key]=(fields[key]&&item.selected[key]!==false)?fields[key]:(current[key]||'')});
  payload.psychosis_signs=Boolean(current.psychosis_signs||fields.psychosis_signs);
  payload.self_harm_concern=Boolean(current.self_harm_concern||fields.self_harm_concern);
  payload.pregnancy_status=fields.pregnancy_status!=='unknown'?fields.pregnancy_status:(current.pregnancy_status||'unknown');
  try{
    await api(`/api/patients/${item.patientId}/clinical-profile`,{method:'PUT',body:JSON.stringify(payload)});
    item.result=null;item.text='';item.file=null;item.filename='';
    await openPatient(item.patientId);
    toast('Клиническая сводка обновлена по истории болезни');
  }catch(error){toast(error.message)}
}

function markHistoryFactors(){
  const factors=state.historyImport.result.therapy_factors;
  if(typeof activatePatientTab==='function')activatePatientTab('therapy',true);
  let marked=0;
  Object.entries(factors).forEach(([key,value])=>{const box=document.querySelector(`#therapy-check-form input[name="${key}"]`);if(box&&value&&!box.checked){box.checked=true;marked++}});
  document.querySelector('#therapy-check-form')?.scrollIntoView({behavior:'smooth',block:'start'});
  toast(marked?`Отмечено факторов: ${marked}. Проверьте и нажмите «Проверить по инструкции»`:'Факторы уже отмечены');
}

const basePatientDetailHistory=patientDetail;
patientDetail=function(){
  const html=basePatientDetailHistory();
  return html.includes('<!--/sheet-->')?html.replace('<!--/sheet-->',historyImportSection()+'<!--/sheet-->'):html;
};

const baseBindHistory=bind;
bind=function(){
  baseBindHistory();
  const item=state.historyImport;
  document.querySelector('#hi-text')?.addEventListener('input',event=>{item.text=event.target.value});
  document.querySelector('#hi-file')?.addEventListener('change',event=>{const file=event.target.files[0];if(!file)return;if(file.size>5*1024*1024){toast('Файл больше 5 МБ');return}item.file=file;item.filename=file.name;render()});
  document.querySelector('[data-hi-run]')?.addEventListener('click',runHistoryImport);
  document.querySelectorAll('[data-hi-field]').forEach(box=>box.addEventListener('change',()=>{item.selected[box.dataset.hiField]=box.checked}));
  document.querySelector('[data-hi-apply]')?.addEventListener('click',applyHistoryImport);
  document.querySelector('[data-hi-factors]')?.addEventListener('click',markHistoryFactors);
};
