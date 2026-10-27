// Экран входа с заставкой Нейрона. Подключается последним, поверх остальных обёрток render/bind.

state.auth={login:'',error:'',sending:false};
const AUTH_DEMO_PATIENTS=[
  ['sokolova','Мария Соколова','стабильная динамика'],
  ['lebedeva','Ольга Лебедева','беременность'],
  ['morozov','Илья Морозов','ухудшение'],
  ['orlova','Елена Орлова','кризис'],
];

function authView(){
  const auth=state.auth;
  return `<main class="auth-screen">
    <div class="auth-glow" aria-hidden="true"></div>
    <section class="auth-splash" aria-hidden="true">
      <span class="auth-spark s1"></span><span class="auth-spark s2"></span><span class="auth-spark s3"></span>
      <img class="auth-neuron" src="assets/neuron/excited.png" alt="" draggable="false">
      <p class="auth-hello">Привет! Я Нейрон</p>
    </section>
    <section class="auth-card">
      <div class="auth-brand"><span class="brand-mark">${icon('heart')}</span><div><b>Клинический компас</b><small>Цифровой ассистент врача и пациента</small></div></div>
      <h1>Вход</h1>
      <div class="auth-demo-warning">${icon('info')}<span><b>Демо-версия.</b> Все пациенты и данные синтетические. Не вводите реальные персональные и медицинские данные — их увидят другие тестирующие. Каждую ночь данные возвращаются к исходным.</span></div>
      ${window.ccAuth.expired?`<div class="notice notice-warn">${icon('clock')} Сессия истекла. Войдите снова.</div>`:''}
      <form id="auth-form" class="auth-form" autocomplete="on">
        <label for="auth-login">Логин</label>
        <input id="auth-login" name="username" autocomplete="username" required maxlength="60" value="${esc(auth.login)}" placeholder="doctor или patient">
        <label for="auth-password">Пароль</label>
        <input id="auth-password" name="password" type="password" autocomplete="current-password" required maxlength="200">
        ${auth.error?`<div class="notice notice-danger">${icon('warning')} ${esc(auth.error)}</div>`:''}
        <button class="btn btn-primary" type="submit" ${auth.sending?'disabled':''}>${auth.sending?'Входим…':'Войти'}</button>
      </form>
      <div class="auth-demo"><span>Демо-доступ</span>
        <button type="button" data-auth-demo="doctor" data-auth-password="doctor2026">${icon('stethoscope')}<b>Врач</b><small>doctor / doctor2026</small></button>
        <button type="button" data-auth-demo="patient" data-auth-password="patient2026">${icon('user')}<b>Пациент</b><small>patient / patient2026</small></button>
        <div class="auth-more"><small>Другие пациенты · пароль patient2026</small><div>${AUTH_DEMO_PATIENTS.map(([login,name,hint])=>`<button type="button" data-auth-demo="${login}" data-auth-password="patient2026" title="${esc(hint)}"><b>${esc(name)}</b><small>${esc(hint)}</small></button>`).join('')}</div></div>
      </div>
      <p class="auth-note">${icon('lock')} Данные демонстрационные. Пароли хранятся только в виде хеша, сессия действует 12 часов.</p>
    </section>
  </main>`;
}

async function authSubmit(login,password){
  const auth=state.auth;
  auth.sending=true;auth.error='';auth.login=login;render();
  try{
    const response=await fetch('/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({login,password})});
    const data=await response.json();
    if(!response.ok)throw new Error(data.detail||'Не удалось войти');
    window.ccAuth.expired=false;window.ccAuth.save(data);
    state.role=data.user.role;state.view='home';saveUI();
    auth.sending=false;auth.login='';
    document.body.classList.add('auth-welcome');setTimeout(()=>document.body.classList.remove('auth-welcome'),900);
    await loadState();
  }catch(error){auth.sending=false;auth.error=error.message;render()}
}

function bindAuth(){
  document.querySelector('#auth-form')?.addEventListener('submit',event=>{
    event.preventDefault();
    authSubmit(document.querySelector('#auth-login').value.trim(),document.querySelector('#auth-password').value);
  });
  document.querySelectorAll('[data-auth-demo]').forEach(button=>button.addEventListener('click',()=>authSubmit(button.dataset.authDemo,button.dataset.authPassword)));
}

async function authLogout(){
  try{await fetch('/api/auth/logout',{method:'POST'})}catch{}
  window.ccAuth.clear();
  window.dispatchEvent(new Event('cc-auth-logout'));
  state.view='home';state.loading=true;state.error=null;
  render();
}

const baseRenderAuth=render;
render=function(){
  if(!window.ccAuth.session){document.querySelector('#app').innerHTML=authView();bindAuth();return}
  baseRenderAuth();
};

const baseBindAuth=bind;
bind=function(){
  baseBindAuth();
  document.querySelectorAll('#role-switch').forEach(node=>{
    const button=node.cloneNode(false);
    button.title='Выйти из учётной записи';
    button.innerHTML=`${icon('logout')}<span>Выйти</span>`;
    button.classList.add('auth-logout');
    button.addEventListener('click',authLogout);
    node.replaceWith(button);
  });
};

window.addEventListener('cc-auth-expired',()=>render());
render();
