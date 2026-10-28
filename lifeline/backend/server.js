// Lifeline server. No dependencies. Needs Node 18+.  Run: node server.js
// Stores every entry in records.json AND every day's data in history/YYYY-MM-DD.json
const http=require('http'),fs=require('fs'),path=require('path');
const APP=path.join(__dirname,'..','frontend','lifeline-app.html'),PORT=process.env.PORT||3000,F='records.json',HDIR='history',MAX=5*1024*1024;
fs.mkdirSync(HDIR,{recursive:true});
let db=[];
if(fs.existsSync(F)){try{db=JSON.parse(fs.readFileSync(F,'utf8'))}catch(e){
  const b='records.corrupt-'+Date.now()+'.json';fs.copyFileSync(F,b);   // never overwrite a damaged file
  console.error('records.json could not be read. Copy kept as '+b)}}
// write to a temp file first, then rename, so a crash or power cut cannot leave a half-written file
const atomic=(f,t)=>{fs.writeFileSync(f+'.tmp',t);fs.renameSync(f+'.tmp',f)};
const cors={'Access-Control-Allow-Origin':'*','Access-Control-Allow-Methods':'GET,POST,OPTIONS','Access-Control-Allow-Headers':'Content-Type'};
const send=(r,c,b,t)=>{r.writeHead(c,{...cors,'Content-Type':t||'text/plain'});r.end(b)};
// Day files are {date, firstSavedAt, updatedAt, data}. Older files (plain data) are still read; their file creation time is used.
const readDay=f=>{const p=path.join(HDIR,f),j=JSON.parse(fs.readFileSync(p,'utf8'));
 if(j&&j.data&&j.firstSavedAt)return j;const st=fs.statSync(p);return{date:f.slice(0,10),firstSavedAt:(st.birthtime||st.mtime).toISOString(),updatedAt:st.mtime.toISOString(),data:j}};
const days=()=>Object.fromEntries(fs.readdirSync(HDIR).filter(f=>/^\d{4}-\d{2}-\d{2}\.json$/.test(f)).sort().map(f=>[f.slice(0,10),readDay(f)]));
// content of an entry, used to tell a real change from a repeat upload of the same data
const body=e=>JSON.stringify([e.data,e.rows,e.row,e.name,e.details,e.status,e.log]);
http.createServer((q,r)=>{
 if(q.method==='OPTIONS'){r.writeHead(204,cors);return r.end()}
 if(q.url==='/health')return send(r,200,'ok');
 if(q.url==='/records'&&q.method==='GET')return send(r,200,JSON.stringify(db,null,1),'application/json');
 if(q.url==='/history'&&q.method==='GET')return send(r,200,JSON.stringify(days(),null,1),'application/json');
 if(q.url==='/records'&&q.method==='POST'){let b='',big=false;
  q.on('data',c=>{b+=c;if(b.length>MAX){big=true;q.destroy()}});
  q.on('end',()=>{if(big)return;try{const e=JSON.parse(b);
    if(!e||typeof e.id!=='string')throw 0;
    const now=new Date().toISOString(),i=db.findIndex(x=>x.id===e.id),p=i<0?null:db[i];
    // ORIGINAL time is fixed the first time an entry is stored and never changed again.
    e.firstSavedAt=(p&&(p.firstSavedAt||p.receivedAt))||e.createdAt||now;
    e.receivedAt=e.firstSavedAt;                       // kept for older tools: now also the original time
    e.updatedAt=(p&&body(p)===body(e))?(p.updatedAt||e.firstSavedAt):now;   // changes only when the data really changed
    if(i<0)db.push(e);else db[i]=e;                     // same id = update, never a duplicate
    if(e.kind==='hist'){if(!/^\d{4}-\d{2}-\d{2}$/.test(e.date))throw 0;
      atomic(path.join(HDIR,e.date+'.json'),JSON.stringify({date:e.date,firstSavedAt:e.firstSavedAt,updatedAt:e.updatedAt,data:e.data},null,1))}
    atomic(F,JSON.stringify(db,null,1));
    send(r,200,JSON.stringify({firstSavedAt:e.firstSavedAt,updatedAt:e.updatedAt}),'application/json')}catch(x){send(r,400,'bad')}});return}
 // open the server address on any device to get the app itself
 if((q.url==='/'||q.url==='/app')&&q.method==='GET'&&fs.existsSync(APP))return send(r,200,fs.readFileSync(APP),'text/html');
 send(r,404,'');
}).listen(PORT,'0.0.0.0',()=>console.log('Lifeline server on http://localhost:'+PORT+'\nAll entries: records.json   Each day: history/YYYY-MM-DD.json'));
