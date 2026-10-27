// Подключается до app.js: хранит сессию и добавляет токен ко всем запросам /api.

const AUTH_KEY='clinical-compass-auth';
window.ccAuth={
  session:(()=>{try{return JSON.parse(localStorage.getItem(AUTH_KEY)||'null')}catch{return null}})(),
  save(session){this.session=session;try{localStorage.setItem(AUTH_KEY,JSON.stringify(session))}catch{}this.syncRole()},
  clear(){this.session=null;try{localStorage.removeItem(AUTH_KEY)}catch{}},
  expired:false,
  syncRole(){
    if(!this.session?.user?.role)return;
    try{const ui=JSON.parse(localStorage.getItem('clinical-compass-ui-v3')||'{}');ui.role=this.session.user.role;localStorage.setItem('clinical-compass-ui-v3',JSON.stringify(ui))}catch{}
  },
};
if(window.ccAuth.session&&new Date(window.ccAuth.session.expires_at)<new Date())window.ccAuth.clear();
window.ccAuth.syncRole();

const nativeFetch=window.fetch.bind(window);
window.fetch=function(input,init={}){
  const url=typeof input==='string'?input:input.url;
  if(!url.startsWith('/api/')||url.startsWith('/api/auth/login'))return nativeFetch(input,init);
  const session=window.ccAuth.session;
  if(!session)return new Promise(()=>{});  // запросы ждут входа, экран входа рисует auth-ui.js
  const headers=new Headers(init.headers||{});
  headers.set('Authorization',`Bearer ${session.token}`);
  headers.delete('X-Demo-Role');
  return nativeFetch(input,{...init,headers}).then(response=>{
    if(response.status===401&&!url.startsWith('/api/auth/')){window.ccAuth.clear();window.ccAuth.expired=true;window.dispatchEvent(new Event('cc-auth-expired'))}
    return response;
  });
};
