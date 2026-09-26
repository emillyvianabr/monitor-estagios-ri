const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const html=fs.readFileSync(require('node:path').join(__dirname,'../index.html'),'utf8');
function setup(){
  const nodes=new Map(), subscriptions=[], writes=[];
  function element(){return {value:'',hidden:false,dataset:{},children:[],listeners:{},style:{},textContent:'',append(...children){this.children.push(...children)},replaceChildren(){this.children=[]},setAttribute(k,v){this[k]=v},addEventListener(k,fn){this.listeners[k]=fn},focus(){},reset(){},querySelector(){return element()}};}
  const document={querySelector(id){if(!nodes.has(id))nodes.set(id,element());return nodes.get(id)},querySelectorAll(){return []},createElement:element};
  document.querySelector('#data').textContent=JSON.stringify({jobs:[],health:[],checkedAt:'2026-09-25'});
  document.querySelector('#relevance').value='all';
  const auth={currentUser:null,onAuthStateChanged(fn){this.change=fn},signOut(){this.currentUser=null;this.change(null)}};
  const ref=path=>({collection:p=>ref(path+'/'+p),doc:p=>ref(path+'/'+p),onSnapshot(ok,error){const sub={path,ok,error,stopped:false};subscriptions.push(sub);return ()=>sub.stopped=true},orderBy(){return this},async get(){return {docs:[]}},async set(data){writes.push({path,data})},async delete(){writes.push({path,deleted:true})},async add(data){writes.push({path,data})}});
  const firestore=()=>({collection:p=>ref(p)});firestore.FieldValue={serverTimestamp:()=>0};
  const context=vm.createContext({document, firebase:{initializeApp(){},auth:()=>auth,firestore},console,URL,TextEncoder,btoa:s=>Buffer.from(s,'binary').toString('base64'),FormData:class{get(){return ''}}});
  for(const match of html.matchAll(/<script>([\s\S]*?)<\/script>/g))vm.runInContext(match[1],context);
  return {context,document,auth,subscriptions,writes,run:code=>vm.runInContext(code,context),login(uid){auth.currentUser={uid,email:uid+'@example.com'};auth.change(auth.currentUser)}};
}
test('normal account, authorized account, revocation and logout',()=>{
  const app=setup();app.login('alice');
  assert.equal(app.document.querySelector('#manual-section').hidden,true);
  app.subscriptions[0].ok({exists:false});assert.equal(app.run('canPublish'),false);
  app.subscriptions[0].ok({exists:true,data:()=>({enabled:true})});
  assert.equal(app.document.querySelector('#manual-section').hidden,false);
  app.subscriptions[0].ok({exists:true,data:()=>({enabled:false})});
  assert.equal(app.document.querySelector('#manual-section').hidden,true);
  app.auth.signOut();assert.equal(app.document.querySelector('#account-area').hidden,true);
  assert.ok(app.subscriptions.every(s=>s.stopped));
});
test('saved jobs write under current UID and toggle removal',async()=>{
  const app=setup();app.login('alice');
  app.run("globalThis.job={url:'https://example.com/job',title:'Estágio',company:'Empresa'};globalThis.button={}");
  await app.run('toggleSaved(job,button)');
  assert.match(app.writes[0].path,/^users\/alice\/saved-jobs\//);
  assert.equal(app.writes[0].data.title,'Estágio');
  app.run('savedJobs.set(jobKey(job),job)');await app.run('toggleSaved(job,button)');
  assert.equal(app.writes[1].deleted,true);
});
test('account changes clear private data and ignore stale callbacks',()=>{
  const app=setup();app.login('alice');const old=app.subscriptions.slice();
  old[1].ok({docs:[{id:'one',data:()=>({title:'Private'})}]});
  assert.equal(app.run('savedJobs.size'),1);
  app.login('bob');assert.equal(app.run('savedJobs.size'),0);
  old[0].ok({exists:true,data:()=>({enabled:true})});
  old[1].ok({docs:[{id:'one',data:()=>({title:'Private'})}]});
  assert.equal(app.run('canPublish'),false);assert.equal(app.run('savedJobs.size'),0);
});
test('anonymous save asks for login without writing',async()=>{
  const app=setup();await app.run("toggleSaved({url:'https://example.com'}, {})");
  assert.equal(app.writes.length,0);assert.match(app.document.querySelector('#auth-msg').textContent,/Entre/);
});
