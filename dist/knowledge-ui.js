state.kb={articles:null,categories:{},query:'',category:'',current:null,returnTo:'knowledge',loading:false,error:null};

const KB_ART={scale:'clipboard',therapy:'pill',protocol:'shield',note:'plan'};
const KB_CATEGORY_FALLBACK={scale:'Шкалы',therapy:'Терапия',protocol:'Протоколы',note:'Заметки врача'};

function kbCategoryName(id){return state.kb.categories[id]||KB_CATEGORY_FALLBACK[id]||id}
function kbDate(value){if(!value)return '';return /^\d{4}-\d{2}-\d{2}$/.test(value)?fmtDue(value):fmtDate(value)}
function kbText(text=''){
  return text.split(/\n{2,}/).map(block=>{
    let lines=block.split('\n');let heading='';
    if(/^##\s+/.test(lines[0])){heading=`<h4>${esc(lines[0].replace(/^##\s+/,''))}</h4>`;lines=lines.slice(1);if(!lines.length)return heading}
    return heading+kbBlock(lines);
  }).join('');
}
function kbBlock(lines){
  if(lines.every(line=>/^\s*[-•]\s+/.test(line)))return `<ul>${lines.map(line=>`<li>${esc(line.replace(/^\s*[-•]\s+/,''))}</li>`).join('')}</ul>`;
  return `<p>${lines.map(esc).join('<br>')}</p>`;
}

async function loadKnowledge(){
  state.kb.loading=true;state.kb.error=null;
  try{
    const params=new URLSearchParams({q:state.kb.query,category:state.kb.category});
    const data=await api(`/api/knowledge?${params}`);
    state.kb.articles=data.articles;state.kb.categories=data.categories;
  }catch(error){state.kb.error=error.message}
  state.kb.loading=false;
  if(state.view==='knowledge'){const box=document.querySelector('#kb-results');if(box){box.innerHTML=kbResults();bind()}else render()}
}

async function openArticle(id,returnTo){
  if(returnTo)state.kb.returnTo=returnTo;
  try{state.kb.current=await api(`/api/knowledge/${encodeURIComponent(id)}`);state.view='kb-article';render();scrollTo(0,0)}
  catch(error){toast(error.message)}
}

function kbCard(article){
  return `<button class="kb-card" data-kb-open="${esc(article.id)}">${art(KB_ART[article.category]||'clipboard','kb-art')}<span class="kb-card-copy"><span class="kb-card-meta"><i class="badge badge-new">${esc(kbCategoryName(article.category))}</i>${article.system?'<i class="kb-source">Из конфигурации</i>':article.template?'<i class="kb-source kb-own">Шаблон · можно править</i>':'<i class="kb-source kb-own">Моя статья</i>'}</span><b>${esc(article.title)}</b>${article.summary?`<small>${esc(article.summary)}</small>`:''}</span>${icon('chevron')}</button>`;
}

function kbResults(){
  const kb=state.kb;
  if(kb.error)return `<div class="card empty compact"><p>${esc(kb.error)}</p></div>`;
  if(!kb.articles)return '<div class="card empty compact"><p>Загружаем базу знаний…</p></div>';
  if(!kb.articles.length)return `<article class="card empty"><span class="status-orb">${icon('search')}</span><h3>Ничего не найдено</h3><p>${kb.query?'Попробуйте другой запрос или категорию.':'В этой категории пока нет статей.'}</p>${kb.category==='note'||!kb.query?`<button class="btn btn-primary" data-kb-new>${icon('plus')} Написать статью</button>`:''}</article>`;
  const own=kb.articles.filter(item=>!item.system);
  const system=kb.articles.filter(item=>item.system);
  const group=(title,items)=>items.length?`<section class="kb-group"><h3>${title}<span>${items.length}</span></h3><div class="kb-list">${items.map(kbCard).join('')}</div></section>`:'';
  return group('Справочник системы',system)+group('Статьи врача',own);
}

function knowledgeView(){
  const kb=state.kb;
  const chips=[['','Все'],...Object.entries(Object.keys(kb.categories).length?kb.categories:KB_CATEGORY_FALLBACK)];
  return shell(`<div class="page-head kb-head"><div><h2>База знаний</h2><p>Шкалы, терапия, протоколы и ваши заметки</p></div><button class="btn btn-primary" data-kb-new>${icon('plus')} <span>Статья</span></button></div>
  <label class="search-bar">${icon('search')}<input id="kb-search" type="search" placeholder="Поиск: эскалация, беременность, PHQ-9…" value="${esc(kb.query)}" autocomplete="off"></label>
  <div class="kb-chips">${chips.map(([id,label])=>`<button class="kb-chip ${kb.category===id?'active':''}" data-kb-category="${id}">${esc(label)}</button>`).join('')}</div>
  <div class="notice notice-neutral kb-notice">${icon('info')} Системные статьи собираются из конфигурации прототипа и всегда совпадают с правилами подсчёта и сигналов.</div>
  <div id="kb-results">${kbResults()}</div>`,'knowledge');
}

function kbSection(section){
  const tone=section.tone?`kb-tone-${section.tone}`:'';
  return `<section class="kb-section ${tone}">${section.title?`<h3>${esc(section.title)}</h3>`:''}${section.text?kbText(section.text):''}${section.items?.length?`<ul>${section.items.map(item=>`<li>${esc(item)}</li>`).join('')}</ul>`:''}${section.table?`<table class="kb-table"><tbody>${section.table.map(row=>`<tr>${row.map((cell,index)=>index?`<td>${esc(cell)}</td>`:`<th>${esc(cell)}</th>`).join('')}</tr>`).join('')}</tbody></table>`:''}</section>`;
}

function articleView(){
  const a=state.kb.current;
  return shell(`<div class="page-head"><button class="back" data-kb-back>${icon('chevron')}</button></div>
  <article class="kb-article"><header class="kb-article-head">${art(KB_ART[a.category]||'clipboard','kb-hero-art')}<div><span class="badge badge-new">${esc(kbCategoryName(a.category))}</span><h2>${esc(a.title)}</h2><p>${esc(a.author||'')}${a.updated_at?` · ${a.system?'версия':'обновлено'} ${esc(kbDate(a.updated_at))}`:''}</p></div></header>
  ${a.summary?`<p class="kb-lead">${esc(a.summary)}</p>`:''}
  ${a.sections.map(kbSection).join('')}
  ${a.tags?.length?`<div class="info-strip">${a.tags.map(tag=>`<button class="chip" data-kb-tag="${esc(tag)}">#${esc(tag)}</button>`).join('')}</div>`:''}
  ${a.links?.length?`<section class="kb-section"><h3>Источники</h3><div class="kb-links">${a.links.map(link=>`<a href="${esc(link.url)}" target="_blank" rel="noreferrer">${icon('book')}<span>${esc(link.label)}</span>${icon('chevron')}</a>`).join('')}</div></section>`:''}
  ${a.system?'<div class="notice notice-neutral">Статья сформирована из конфигурации и обновится сама при изменении правил.</div>':`<div class="kb-actions"><button class="btn btn-secondary" data-kb-edit>${icon('edit')} Редактировать</button><button class="btn btn-danger-soft" data-kb-delete>Удалить</button></div>`}
  </article>`,'knowledge');
}

function articleEditView(){
  const a=state.kb.current&&!state.kb.current.system&&state.kb.editing?state.kb.current:{title:'',category:state.kb.category&&state.kb.category!=='scale'?state.kb.category:'note',summary:'',body:'',tags:[],source_url:''};
  const categories=Object.keys(KB_CATEGORY_FALLBACK);
  return shell(`<div class="page-head"><button class="back" data-kb-cancel>${icon('chevron')}</button><h2>${state.kb.editing?'Редактирование':'Новая статья'}</h2><p>Протокол, памятка или заметка для работы с пациентами</p></div>
  <form class="form-card kb-form" id="kb-form">
    <div class="field"><label for="kb-title">Название</label><input class="text-input" id="kb-title" name="title" maxlength="200" required value="${esc(a.title)}" placeholder="Например, протокол первичного приёма"></div>
    <div class="form-grid"><div class="field"><label for="kb-category">Категория</label><select id="kb-category" name="category">${categories.map(id=>`<option value="${id}" ${a.category===id?'selected':''}>${esc(kbCategoryName(id))}</option>`).join('')}</select></div>
    <div class="field"><label for="kb-tags">Теги через запятую</label><input class="text-input" id="kb-tags" name="tags" value="${esc((a.tags||[]).join(', '))}" placeholder="тревога, первичный приём"></div></div>
    <div class="field"><label for="kb-summary">Кратко</label><input class="text-input" id="kb-summary" name="summary" maxlength="500" value="${esc(a.summary||'')}" placeholder="Одна строка о содержании"></div>
    <div class="field"><label for="kb-body">Текст</label><small>Пустая строка — новый абзац. «## Заголовок» — подраздел, строки с «- » станут списком.</small><textarea id="kb-body" name="body" rows="12" maxlength="20000" required>${esc(a.body||'')}</textarea></div>
    <div class="field"><label for="kb-source">Источник (ссылка)</label><input class="text-input" id="kb-source" name="source_url" type="url" maxlength="500" value="${esc(a.source_url||'')}" placeholder="https://"></div>
    <button class="btn btn-primary btn-wide" type="submit">${icon('check')} Сохранить</button>
  </form>`,'knowledge');
}

function patientKnowledgeBlock(){
  const links=[];
  const scales=[...new Set(state.assessments.map(item=>item.scale_id))];
  scales.forEach(id=>{const scale=scaleById(id);if(scale)links.push([id,`Интерпретация ${scale.name}`])});
  if(state.checkins.length||state.adherence?.total)links.push(['aviandr','АВИАНДР®: противопоказания']);
  if(state.routingSignals.length)links.push(['routing','Сигналы и маршрутизация']);
  if(state.routingSignals.some(signal=>signal.level==='mandatory'))links.push(['alerting','Критический алертинг']);
  if(!links.length)links.push(['routing','Сигналы и маршрутизация']);
  return `<section class="section"><article class="card kb-patient"><div class="section-head"><h3>Материалы по пациенту</h3><button class="text-btn" data-view="knowledge">Вся база ${icon('chevron')}</button></div><div class="kb-patient-links">${links.map(([id,label])=>`<button data-kb-open="${id}" data-kb-from="patient">${art(KB_ART[id==='aviandr'?'therapy':['routing','alerting'].includes(id)?'protocol':'scale'],'kb-mini-art')}<span>${esc(label)}</span>${icon('chevron')}</button>`).join('')}</div></article></section>`;
}

const basePatientDetailKnowledge=patientDetail;
patientDetail=function(){
  const html=basePatientDetailKnowledge();
  const marker='<div class="detail-grid section">';
  return html.includes(marker)?html.replace(marker,patientKnowledgeBlock()+marker):html;
}

const baseRenderKnowledge=render;
render=function(){
  if(!state.loading&&!state.error&&state.role==='doctor'&&['knowledge','kb-article','kb-edit'].includes(state.view)){
    if(state.view==='kb-article'&&!state.kb.current)state.view='knowledge';
    if(state.view==='knowledge'&&!state.kb.articles&&!state.kb.loading)loadKnowledge();
    document.querySelector('#app').innerHTML=state.view==='knowledge'?knowledgeView():state.view==='kb-article'?articleView():articleEditView();
    bind();return;
  }
  baseRenderKnowledge();
}

const baseBindKnowledge=bind;
bind=function(){
  baseBindKnowledge();
  const search=document.querySelector('#kb-search');
  search?.addEventListener('input',()=>{clearTimeout(bind.kbTimer);bind.kbTimer=setTimeout(()=>{state.kb.query=search.value.trim();loadKnowledge()},250)});
  document.querySelectorAll('[data-kb-category]').forEach(button=>button.addEventListener('click',()=>{
    state.kb.category=button.dataset.kbCategory;
    document.querySelectorAll('[data-kb-category]').forEach(chip=>chip.classList.toggle('active',chip===button));
    loadKnowledge();
  }));
  document.querySelectorAll('[data-kb-open]').forEach(button=>button.addEventListener('click',event=>{
    event.stopPropagation();openArticle(button.dataset.kbOpen,button.dataset.kbFrom||'knowledge');
  }));
  document.querySelectorAll('[data-kb-tag]').forEach(button=>button.addEventListener('click',()=>{
    state.kb.query=button.dataset.kbTag;state.kb.category='';state.kb.articles=null;state.view='knowledge';render();scrollTo(0,0);
  }));
  document.querySelector('[data-kb-back]')?.addEventListener('click',()=>{
    if(state.kb.returnTo==='patient'&&state.currentPatient){state.view='patient';render()}
    else{state.view='knowledge';state.kb.articles=null;render()}
    scrollTo(0,0);
  });
  document.querySelectorAll('[data-kb-new]').forEach(button=>button.addEventListener('click',()=>{state.kb.editing=false;state.view='kb-edit';render();scrollTo(0,0)}));
  document.querySelector('[data-kb-edit]')?.addEventListener('click',()=>{state.kb.editing=true;state.view='kb-edit';render();scrollTo(0,0)});
  document.querySelector('[data-kb-cancel]')?.addEventListener('click',()=>{state.view=state.kb.editing?'kb-article':'knowledge';render();scrollTo(0,0)});
  document.querySelector('[data-kb-delete]')?.addEventListener('click',async()=>{
    if(!confirm(`Удалить статью «${state.kb.current.title}»?`))return;
    try{await api(`/api/knowledge/${state.kb.current.id}`,{method:'DELETE'});state.kb.current=null;state.kb.articles=null;state.view='knowledge';render();toast('Статья удалена')}
    catch(error){toast(error.message)}
  });
  document.querySelector('#kb-form')?.addEventListener('submit',async event=>{
    event.preventDefault();const form=event.target;const button=event.submitter;
    const value=name=>form.elements[name].value.trim();
    if(!value('title')||!value('body')){toast('Заполните название и текст');return}
    if(value('source_url')&&!/^https?:\/\/\S+$/.test(value('source_url'))){toast('Ссылка должна начинаться с http:// или https://');return}
    const payload={title:value('title'),category:form.elements.category.value,summary:value('summary'),body:value('body'),source_url:value('source_url'),tags:value('tags').split(',').map(tag=>tag.trim()).filter(Boolean).slice(0,10)};
    button.disabled=true;
    try{
      const editing=state.kb.editing;
      state.kb.current=await api(editing?`/api/knowledge/${state.kb.current.id}`:'/api/knowledge',{method:editing?'PUT':'POST',body:JSON.stringify(payload)});
      state.kb.editing=false;state.kb.articles=null;state.kb.returnTo='knowledge';state.view='kb-article';render();scrollTo(0,0);
      toast(editing?'Статья обновлена':'Статья добавлена в базу знаний');
    }catch(error){button.disabled=false;toast(error.message)}
  });
}
