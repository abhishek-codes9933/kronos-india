'use strict';
const liveSeries=new Map();
let livePaused=false;
function appendLivePoint(rows,price,time){
 if(!Number.isFinite(price)||price<=0||!Number.isFinite(time))return;
 if(rows.length&&time<=rows.at(-1).time)return;
 rows.push({price,time});
 while(rows.length&&(rows[0].time<time-3600000||rows.length>900))rows.shift();
}
function recordLive(data){
 if(!connected)return;
 const keep=new Set([selected.key,...watch.map(x=>x.key)]);
 for(const key of liveSeries.keys())if(!keep.has(key))liveSeries.delete(key);
 for(const [key,q] of Object.entries(data.quotes)){
  if(!keep.has(key))continue;
  if(!liveSeries.has(key))liveSeries.set(key,[]);
  appendLivePoint(liveSeries.get(key),q.price,Date.parse(data.received_at));
 }
 drawLive();
}
function drawLive(){
 if(!connected){liveSeries.clear();$('liveChart').replaceChildren();$('liveStatus').textContent='Connect Dhan to start';return;}
 if(livePaused){$('liveStatus').textContent='Display paused · quotes continue collecting';return;}
 const now=Date.now(),span=Number($('liveRange').value)*60000;
 const rows=(liveSeries.get(selected.key)||[]).filter(r=>r.time>=now-span);
 if(!rows.length){$('liveChart').replaceChildren();$('liveStatus').textContent='Waiting for a quote for this instrument…';return;}
 const last=rows.at(-1),stale=now-last.time>15000;
 const time=t=>new Date(t).toLocaleTimeString('en-GB',{timeZone:'Asia/Kolkata'});
 $('liveStatus').textContent=(stale?'Delayed · last receipt ':'5s snapshots · received ')+time(last.time)+' IST';
 const low=Math.min(...rows.map(r=>r.price)),high=Math.max(...rows.map(r=>r.price)),pad=Math.max((high-low)*.15,high*.0001,.01);
 const x=t=>22+(t-now+span)/span*870,y=v=>20+(high+pad-v)/(high-low+2*pad)*200;
 let svg='';
 for(let i=0;i<5;i++){const v=low-pad+(high-low+2*pad)*i/4;svg+=`<line x1="22" y1="${y(v)}" x2="892" y2="${y(v)}" stroke="#edf0ec"/><text x="905" y="${y(v)+4}" fill="#71808a" font-size="11">${v.toFixed(2)}</text>`;}
 let group=[],groups=[];
 for(const r of rows){if(group.length&&r.time-group.at(-1).time>15000){groups.push(group);group=[];}group.push(r);}groups.push(group);
 for(const points of groups)svg+=`<polyline fill="none" stroke="#147b65" stroke-width="2.5" points="${points.map(r=>`${x(r.time)},${y(r.price)}`).join(' ')}"/>`;
 svg+=`<circle cx="${x(last.time)}" cy="${y(last.price)}" r="4" fill="${stale?'#c6a35f':'#147b65'}"/>`;
 for(let i=0;i<4;i++)svg+=`<text x="${22+870*i/3}" y="248" text-anchor="${i===0?'start':i===3?'end':'middle'}" fill="#71808a" font-size="11">${time(now-span+span*i/3)}</text>`;
 $('liveChart').innerHTML=svg;
 $('liveChart').setAttribute('aria-label',`${selected.symbol}: ${rows.length} Dhan snapshots. Last price ${fmt(last.price)}.`);
}
const $=id=>document.getElementById(id);
const nonce=document.querySelector('meta[name="app-token"]').content;
const fmt=n=>Number.isFinite(n)?n.toLocaleString('en-IN',{maximumFractionDigits:2,minimumFractionDigits:2}):'—';
let selected={key:'IDX_I:13',id:'13',symbol:'NIFTY 50',name:'Nifty 50',segment:'IDX_I',instrument:'INDEX',expiry:''};
let connected=false,history=null,prediction=null,chartMode='candles',loading=false,busy=false,jobID=null,historySeq=0,searchSeq=0,quoteBusy=false;
let watch=[];try{watch=JSON.parse(localStorage.getItem('kronos-watchlist')||'[]').filter(x=>x&&typeof x.key==='string'&&typeof x.symbol==='string').slice(0,30);}catch{}
let quotes={};
function notify(text){$('message').textContent=text;$('message').hidden=!text;}
async function api(path,body){
 const options=body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json','X-Kronos-Token':nonce},body:JSON.stringify(body)};
 const r=await fetch(path,options);let d;try{d=await r.json();}catch{throw new Error('The local app is not responding. Restart it with Start Kronos India.cmd.');}
 if(!r.ok)throw new Error(d.error||'Request failed.');return d;
}
function resetForecast(){prediction=null;$('forecastResult').hidden=true;$('forecastStatus').textContent=busy?'A forecast is running. Its result will appear for the selected instrument.':'Ready when 400 completed candles are available.';}
function updateButton(){ $('forecast').disabled=busy||loading||!history||history.rows.length<400; $('forecast').textContent=busy?'◌ Kronos is forecasting…':'✳ Generate forecast';}
function setSelected(item){selected=item;livePaused=false;$("livePause").textContent="Pause";$("livePause").setAttribute("aria-pressed","false");drawLive();history=null;resetForecast();$('instrumentTitle').textContent=item.name||item.symbol;$('instrumentMeta').textContent=`${item.segment.replace('_',' / ')} · ${item.instrument}`;$('instrumentDetail').textContent=[item.symbol,item.expiry?`Expiry ${item.expiry}`:'',item.option&&item.option!=='XX'?`${item.option} ${item.strike}`:''].filter(Boolean).join(' · ');$('model').options[1].disabled=item.key!=='IDX_I:13';if(item.key!=='IDX_I:13')$('model').value='original';$('watchAdd').textContent=watch.some(x=>x.key===item.key)?'✓ In watchlist':'+ Watchlist';if(item.key!=='IDX_I:13')$('source').value='dhan';renderWatch();loadHistory();renderSearchActive();refreshQuotes();}
function renderSearchActive(){document.querySelectorAll('.result').forEach(el=>el.classList.toggle('active',el.dataset.key===selected.key));}
async function search(){const seq=++searchSeq;try{const data=await api(`/api/search?q=${encodeURIComponent($('search').value)}&segment=${encodeURIComponent($('segment').value)}`);if(seq!==searchSeq)return;$('results').replaceChildren();$('resultsCount').textContent=`${data.total.toLocaleString()} MATCHES`;for(const item of data.items){const b=document.createElement('button');b.className='result';b.dataset.key=item.key;const strong=document.createElement('strong');strong.textContent=item.name||item.symbol;const small=document.createElement('small');small.textContent=`${item.segment} · ${item.instrument}${item.expiry?' · '+item.expiry:''}`;b.append(strong,small);b.onclick=()=>setSelected(item);$('results').append(b);}if(!data.items.length){const p=document.createElement('p');p.className='small muted';p.textContent='No matching instruments. Try another symbol or refresh the catalogue.';$('results').append(p);}renderSearchActive();}catch(e){notify(e.message);}}
function renderWatch(){ $('watchlist').replaceChildren();$('watchCount').textContent=`${watch.length}/30`;for(const item of watch){const row=document.createElement('div');row.className='watch-item';const button=document.createElement('button');const title=document.createElement('strong');title.textContent=item.symbol;const sub=document.createElement('small');sub.textContent=item.segment;button.append(title,sub);button.onclick=()=>setSelected(item);const price=document.createElement('span');price.className='watch-price';price.textContent=fmt(quotes[item.key]?.price);const remove=document.createElement('button');remove.className='watch-remove';remove.textContent='×';remove.setAttribute('aria-label',`Remove ${item.symbol} from watchlist`);remove.onclick=()=>{watch=watch.filter(x=>x.key!==item.key);saveWatch();};row.append(button,price,remove);$('watchlist').append(row);}if(!watch.length){const p=document.createElement('p');p.className='small muted';p.textContent='Add instruments to follow their latest quotes.';$('watchlist').append(p);}}
function saveWatch(){localStorage.setItem('kronos-watchlist',JSON.stringify(watch));renderWatch();$('watchAdd').textContent=watch.some(x=>x.key===selected.key)?'✓ In watchlist':'+ Watchlist';}
async function loadHistory(){const seq=++historySeq;const key=selected.key,source=$('source').value;loading=true;history=null;resetForecast();updateButton();$('chartState').hidden=false;$('chartState').textContent='Loading completed five-minute candles…';$('chart').replaceChildren();draw();$('price').textContent='—';$('asOf').textContent='—';try{if(source==='dhan'&&!connected)throw new Error('Connect Dhan to view this instrument’s market data.');const result=await api(`/api/history?key=${encodeURIComponent(key)}&source=${source}`);if(seq!==historySeq)return;history=result;$('asOf').textContent=result.as_of.replace(':00','').slice(5,16);$('dataSource').textContent=source==='sample'?'Saved historical data · not live':'Dhan · completed candles';$('priceLabel').textContent='LAST COMPLETED CLOSE';$('price').textContent=fmt(result.rows.at(-1).close);$('priceDetail').textContent=`${result.rows.length} candles loaded`;const lastMs=Date.parse(result.as_of.replace(' ','T')+'+05:30'),age=(Date.now()-lastMs)/60000;$('chartState').hidden=false;$('chartState').textContent=source==='sample'?'Historical preview — connect Dhan for fresh market data.':age>15?'Latest available candles are older than 15 minutes. The market may be closed or data delayed.':'Completed five-minute candles · incomplete candle excluded.';draw();if(connected&&source==='dhan')refreshQuotes();}catch(e){if(seq===historySeq){$('chartState').hidden=false;$('chartState').textContent=e.message;}}finally{if(seq===historySeq){loading=false;updateButton();}}}
async function refreshQuotes(){if(!connected||quoteBusy)return;quoteBusy=true;const keys=[...new Set([selected.key,...watch.map(x=>x.key)])].slice(0,30);try{const data=await api('/api/quotes?keys='+encodeURIComponent(keys.join(',')));quotes={...quotes,...data.quotes};recordLive(data);renderWatch();if($('source').value==='dhan'&&quotes[selected.key]?.price!=null){const q=quotes[selected.key];$('priceLabel').textContent='LATEST DHAN QUOTE';$('price').textContent=fmt(q.price);$('priceDetail').textContent=`${q.change_percent==null?'':(q.change_percent>=0?'+':'')+q.change_percent.toFixed(2)+'% · '}Received ${data.received_at.slice(11)} IST`;$('priceDetail').title='Receipt time, not exchange trade time. Closed markets may return the last available quote.';}$('connectionStatus').textContent='Dhan connected · 5s snapshots';$('connectionDot').className='dot connected';}catch(e){$('connectionStatus').textContent='Quote refresh unavailable';$('connectionDot').className='dot';$('priceDetail').textContent='Quote may be stale · '+e.message;}finally{quoteBusy=false;}}
function draw(){if(window.renderWorkbench)window.renderWorkbench();}
async function generate(){if(busy||!history)return;notify('');prediction=null;draw();$('forecastResult').hidden=true;busy=true;updateButton();$('forecastStatus').textContent='Generating the selected scenario. The first run also loads the model.';try{const r=await api('/api/forecast',{key:selected.key,source:$('source').value,model:$('model').value,horizon:Number($('horizon').value),speed:$('speed').value});jobID=r.id;pollJob();}catch(e){busy=false;updateButton();$('forecastStatus').textContent=e.message;}}
async function pollJob(){try{const j=await api('/api/job');if(j.id!==jobID){busy=false;updateButton();return;}if(j.status==='running'){setTimeout(pollJob,500);return;}busy=false;updateButton();if(j.status==='error'){$('forecastStatus').textContent=j.error;return;}const r=j.result;if(r.instrument.key!==selected.key||r.source!==$('source').value||r.model!==$('model').value||r.speed!==$('speed').value||r.rows.length!==Number($('horizon').value)||!history||r.as_of!==history.as_of){$('forecastStatus').textContent='Previous instrument’s forecast completed. Generate a new forecast for this selection.';return;}prediction=r;draw();$('forecastResult').hidden=false;$('forecastPrice').textContent=fmt(r.rows.at(-1).close);const previous=history.rows.at(-1).close,change=(r.rows.at(-1).close/previous-1)*100;$('forecastChange').textContent=`${change>=0?'+':''}${change.toFixed(2)}% from last candle · ${r.rows.length} projected candles`;$('forecastStatus').textContent=`${r.cache_hit?'Reused matching result':'Completed'} in ${r.elapsed_seconds}s on ${r.device.toUpperCase()} · ${r.paths} path(s) · ${r.source==='sample'?'historical scenario':'based on latest loaded candles'}.`;}catch(e){busy=false;updateButton();$('forecastStatus').textContent=e.message;}}
function csvDownload(rows,name){if(!rows?.length)return;const cols=Object.keys(rows[0]);const escape=v=>'"'+String(v??'').replaceAll('"','""')+'"';const text=[cols.map(escape).join(','),...rows.map(r=>cols.map(k=>escape(r[k])).join(','))].join('\r\n');const url=URL.createObjectURL(new Blob([text],{type:'text/csv'}));const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
$('connectOpen').onclick=()=>{$('connectError').textContent='';$('connectDialog').showModal();};$('closeDialog').onclick=()=>$('connectDialog').close();$('connectForm').onsubmit=async e=>{e.preventDefault();$('connectSubmit').disabled=true;$('connectError').textContent='Checking Dhan access…';const token=$('token').value;$('token').value='';try{await api('/api/connect',{client:$('client').value,token});connected=true;$('connectDialog').close();$('connectOpen').textContent='Dhan connected ↗';$('source').value='dhan';notify('');loadHistory();refreshQuotes();}catch(e){$('connectError').textContent=e.message;}finally{$('connectSubmit').disabled=false;}};
$('disconnect').onclick=async()=>{try{await api('/api/disconnect',{});connected=false;quotes={};drawLive();$('connectionStatus').textContent='Disconnected';$('connectionDot').className='dot';$('connectOpen').textContent='Connect Dhan ↗';$('connectDialog').close();$('source').value='sample';setSelected({key:'IDX_I:13',id:'13',symbol:'NIFTY 50',name:'Nifty 50',segment:'IDX_I',instrument:'INDEX'});}catch(e){$('connectError').textContent=e.message;}};
let debounce;$('search').oninput=()=>{clearTimeout(debounce);debounce=setTimeout(search,220);};$('segment').onchange=search;
$('watchAdd').onclick=()=>{if(watch.some(x=>x.key===selected.key))return;if(watch.length>=29){notify('Keep up to 29 instruments in the watchlist, plus the currently selected instrument.');return;}watch.push(selected);saveWatch();refreshQuotes();};
$('refreshCatalogue').onclick=async()=>{const b=$('refreshCatalogue');b.disabled=true;notify('Refreshing Dhan’s public instrument catalogue…');try{const r=await api('/api/catalogue',{});$('catalogueCount').textContent=`${r.instruments.toLocaleString()} instruments`;notify('Catalogue refreshed.');search();}catch(e){notify(e.message);}finally{b.disabled=false;}};
$('source').onchange=()=>{resetForecast();loadHistory();};$('model').onchange=()=>{resetForecast();draw();};$('horizon').onchange=()=>{resetForecast();draw();};$('refreshHistory').onclick=loadHistory;$('forecast').onclick=generate;
$('candlesTab').onclick=()=>{chartMode='candles';$('candlesTab').classList.add('selected');$('lineTab').classList.remove('selected');draw();};$('lineTab').onclick=()=>{chartMode='line';$('lineTab').classList.add('selected');$('candlesTab').classList.remove('selected');draw();};
$('exportHistory').onclick=()=>csvDownload(history?.rows,`${selected.key.replace(':','_')}_5min_${history?.source||'data'}.csv`);$('exportForecast').onclick=()=>csvDownload(prediction?.rows.map(r=>({...r,instrument:prediction.instrument.symbol,model:prediction.model,speed:prediction.speed,paths:prediction.paths,source:prediction.source,as_of:prediction.as_of,calendar:'approximate weekday sessions'})),`${selected.key.replace(':','_')}_forecast.csv`);
function clock(){$('clock').textContent=new Date().toLocaleString('en-IN',{timeZone:'Asia/Kolkata',day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'})+' IST';}clock();setInterval(clock,30000);setInterval(refreshQuotes,5000);setInterval(()=>{if(connected&&$('source').value==='dhan'&&!busy&&!loading)refreshCompleted();},60000);
async function start(){try{const s=await api('/api/status');connected=s.connected;$('catalogueCount').textContent=`${s.instruments.toLocaleString()} instruments`;$('catalogueCount').title='Catalogue refreshed: '+s.catalogue_date;if(connected){$('source').value='dhan';$('connectOpen').textContent='Dhan connected ↗';}$('model').options[1].disabled=!s.nifty_model;await search();renderWatch();await loadHistory();}catch(e){notify(e.message);}}start();

$("liveRange").onchange=drawLive;
$("livePause").onclick=()=>{livePaused=!livePaused;$("livePause").textContent=livePaused?"Resume":"Pause";$("livePause").setAttribute("aria-pressed",String(livePaused));drawLive();};
setInterval(drawLive,5000);

async function refreshCompleted(){
 const key=selected.key,seq=historySeq;
 try{const next=await api('/api/history?key='+encodeURIComponent(key)+'&source=dhan');
 if(seq!==historySeq||key!==selected.key||$('source').value!=='dhan')return;
 if(history&&JSON.stringify(next.rows)===JSON.stringify(history.rows))return;
 history=next;resetForecast();$('asOf').textContent=next.as_of.slice(5,16);draw();updateButton();
 }catch(e){notify('Candle refresh unavailable: '+e.message);}
}
$('speed').onchange=()=>{$('pathCount').textContent=$('speed').value==='fast'?'1':'3';resetForecast();draw();};
