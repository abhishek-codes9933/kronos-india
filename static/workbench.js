'use strict';
(() => {
 const svg=$('chart');
 let frame=5,bars=90,offset=0,tool='cursor',pending=null,drag=null,geometry=null,lastKey='',hover=null;
 let drawings={};try{drawings=JSON.parse(localStorage.getItem('kronos-drawings')||'{}');if(!drawings||Array.isArray(drawings)||typeof drawings!=='object')drawings={};}catch{}
 const palette={up:'#26b8a6',down:'#ef6675',text:'#8793aa',grid:'#202634',sma:'#edb95e',ema:'#7b9eff',ai:'#af8aff'};
 const esc=s=>String(s).replace(/[<>&"']/g,c=>({'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;',"'":'&#39;'}[c]));
 const key=()=>selected.key+'|'+$('source').value+'|'+frame;
 const validPoint=p=>p&&typeof p.stamp==='string'&&/^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d$/.test(p.stamp)&&Number.isFinite(p.price);
 function lines(){const a=drawings[key()];return Array.isArray(a)?a.filter(d=>d&&['trend','horizontal'].includes(d.type)&&validPoint(d.a)&&(d.type==='horizontal'||validPoint(d.b))).slice(-100):[];}
 function save(list){drawings[key()]=list;const keys=Object.keys(drawings);while(keys.length>50)delete drawings[keys.shift()];try{localStorage.setItem('kronos-drawings',JSON.stringify(drawings));}catch{notify('Drawing storage is full. Current drawings remain in this page.');}}
 function setTool(value){tool=value;pending=null;document.querySelectorAll('[data-tool]').forEach(b=>{b.classList.toggle('selected',b.dataset.tool===tool);b.setAttribute('aria-pressed',String(b.dataset.tool===tool));});$('toolHint').textContent=tool==='trend'?'Click two points to draw a trend line · Esc cancels':tool==='horizontal'?'Click a price to draw a horizontal level':'Scroll to zoom · drag to pan · arrow keys to pan';render();}
 function render(){
  if(!history){svg.replaceChildren();geometry=null;return;}
  if(lastKey!==key()){offset=0;pending=null;hover=null;lastKey=key();}
  const all=aggregateCandles(history.rows,frame,['MCX_COMM','NSE_CURRENCY','BSE_CURRENCY'].includes(selected.segment)?0:15);
  offset=Math.max(0,Math.min(offset,Math.max(0,all.length-10)));
  const end=all.length-Math.round(offset),start=Math.max(0,end-Math.round(bars)),rows=all.slice(start,end);
  if(!rows.length)return;
  const forecast=frame===5&&offset<1?(prediction?.rows||[]):[];
  const W=Math.max(600,svg.clientWidth||1000),H=Math.max(320,svg.clientHeight||500),L=12,R=86,T=38;
  const volume=$('showVolume').checked,rsiOn=$('showRSI').checked;
  const volumeH=volume?Math.min(70,H*.13):0,rsiH=rsiOn?Math.min(100,H*.19):0;
  const bottom=H-28,priceBottom=bottom-volumeH-rsiH-10;
  const vals=[...rows,...forecast],low=Math.min(...vals.map(r=>r.low)),high=Math.max(...vals.map(r=>r.high));
  const pad=Math.max((high-low)*.09,Math.abs(high)*.0001,.01),min=low-pad,max=high+pad;
  const count=rows.length+Math.max(10,forecast.length+3),step=(W-L-R)/count;
  const x=i=>L+(i+.5)*step,y=v=>T+(max-v)/(max-min)*(priceBottom-T);
  const bw=Math.max(1,step*.65);
  geometry={all,rows,start,end,x,y,W,H,L,R,T,bottom,priceBottom,min,max,step};
  svg.setAttribute('viewBox',`0 0 ${W} ${H}`);
  let out=`<defs><clipPath id="priceClip"><rect x="${L}" y="${T}" width="${W-L-R}" height="${priceBottom-T}"/></clipPath></defs>`;
  for(let i=0;i<6;i++){const v=min+(max-min)*i/5,yy=y(v);out+=`<line x1="0" x2="${W-R}" y1="${yy}" y2="${yy}" stroke="${palette.grid}"/><text x="${W-R+10}" y="${yy+4}" fill="${palette.text}" font-size="11">${fmt(v)}</text>`;}
  const stride=Math.max(1,Math.ceil(rows.length/6));
  for(let i=0;i<rows.length;i+=stride){out+=`<line x1="${x(i)}" x2="${x(i)}" y1="${T}" y2="${bottom}" stroke="${palette.grid}"/><text x="${x(i)}" y="${H-8}" text-anchor="${i===0?'start':'middle'}" fill="${palette.text}" font-size="10">${esc(rows[i].timestamp.slice(5,16))}</text>`;}
  out+='<g clip-path="url(#priceClip)">';
  if(chartMode==='candles')rows.forEach((r,i)=>{const color=r.close>=r.open?palette.up:palette.down;out+=`<g opacity="${r.partial?.65:1}"><line x1="${x(i)}" x2="${x(i)}" y1="${y(r.high)}" y2="${y(r.low)}" stroke="${color}"/><rect x="${x(i)-bw/2}" y="${Math.min(y(r.open),y(r.close))}" width="${bw}" height="${Math.max(1,Math.abs(y(r.open)-y(r.close)))}" fill="${color}"/></g>`;});
  else out+=`<polyline fill="none" stroke="${palette.up}" stroke-width="1.8" points="${rows.map((r,i)=>`${x(i)},${y(r.close)}`).join(' ')}"/>`;
  const closes=all.map(r=>r.close),series=[];
  if($('showSMA').checked)series.push([sma(closes,20),palette.sma,'SMA 20']);
  if($('showEMA').checked)series.push([ema(closes,50),palette.ema,'EMA 50']);
  for(const [data,color] of series){out+=`<polyline fill="none" stroke="${color}" stroke-width="1.4" points="${data.slice(start,end).map((v,i)=>v===null?'':`${x(i)},${y(v)}`).filter(Boolean).join(' ')}"/>`;}
  if(forecast.length){const edge=x(rows.length)-step/2;out+=`<rect x="${edge}" y="${T}" width="${W-R-edge}" height="${priceBottom-T}" fill="${palette.ai}" opacity=".07"/><line x1="${edge}" x2="${edge}" y1="${T}" y2="${priceBottom}" stroke="${palette.ai}" stroke-dasharray="4 4"/><polyline fill="none" stroke="${palette.ai}" stroke-width="2" stroke-dasharray="5 3" points="${[[x(rows.length-1),y(rows.at(-1).close)],...forecast.map((r,i)=>[x(rows.length+i),y(r.close)])].map(p=>p.join(',')).join(' ')}"/><text x="${edge+6}" y="${T+15}" fill="${palette.ai}" font-size="10">KRONOS</text>`;}
  const latest=rows.at(-1),yy=y(latest.close);out+=`<line x1="${L}" x2="${W-R}" y1="${yy}" y2="${yy}" stroke="${latest.close>=latest.open?palette.up:palette.down}" opacity=".5" stroke-dasharray="2 4"/>`;
  const pointIndex=p=>all.findIndex(r=>r.timestamp===p.stamp)-start;
  for(const d of lines()){
   if(d.type==='horizontal')out+=`<line x1="${L}" x2="${W-R}" y1="${y(d.a.price)}" y2="${y(d.a.price)}" stroke="#68a9ff" stroke-width="1.4"/><text x="${L+5}" y="${y(d.a.price)-5}" fill="#68a9ff" font-size="10">${fmt(d.a.price)}</text>`;
   else{const a=pointIndex(d.a),b=pointIndex(d.b);if(a>=-start&&b>=-start)out+=`<line x1="${x(a)}" x2="${x(b)}" y1="${y(d.a.price)}" y2="${y(d.b.price)}" stroke="#68a9ff" stroke-width="2"/>`;}
  }
  if(pending){const i=pointIndex(pending);out+=`<circle cx="${x(i)}" cy="${y(pending.price)}" r="4" fill="#68a9ff"/>`;}
  out+='</g>';
  out+=`<rect x="${W-R}" y="${yy-9}" width="${R}" height="18" fill="${latest.close>=latest.open?palette.up:palette.down}"/><text x="${W-R+7}" y="${yy+4}" fill="#07171b" font-size="11">${fmt(latest.close)}</text>`;
  const quote=connected&&$('source').value==='dhan'?quotes[selected.key]?.price:null;
  if(Number.isFinite(quote)&&quote>=min&&quote<=max&&offset<1)out+=`<line x1="${L}" x2="${W-R}" y1="${y(quote)}" y2="${y(quote)}" stroke="#e7ce82" stroke-dasharray="6 4"/><text x="${L+4}" y="${y(quote)-5}" fill="#e7ce82" font-size="10">DHAN SNAPSHOT ${fmt(quote)}</text>`;
  let panelTop=priceBottom+10;
  if(volume){const maxVol=Math.max(1,...rows.map(r=>r.volume));out+=`<text x="12" y="${panelTop+12}" fill="${palette.text}" font-size="10">VOLUME${selected.instrument==='INDEX'?' · not reported for index':''}</text>`;rows.forEach((r,i)=>{const h=r.volume/maxVol*(volumeH-18);out+=`<rect x="${x(i)-bw/2}" y="${panelTop+volumeH-h}" width="${bw}" height="${h}" fill="${r.close>=r.open?palette.up:palette.down}" opacity=".35"/>`;});panelTop+=volumeH;}
  if(rsiOn){const values=rsi(closes,14).slice(start,end),ry=v=>panelTop+15+(100-v)/100*(rsiH-18);out+=`<line x1="0" x2="${W}" y1="${panelTop}" y2="${panelTop}" stroke="${palette.grid}"/><text x="12" y="${panelTop+12}" fill="${palette.ai}" font-size="10">RSI 14 · ${fmt(values.at(-1))}</text>`;for(const v of [30,70])out+=`<line x1="${L}" x2="${W-R}" y1="${ry(v)}" y2="${ry(v)}" stroke="#50425f" stroke-dasharray="3 5"/><text x="${W-R+10}" y="${ry(v)+4}" fill="${palette.text}" font-size="10">${v}</text>`;out+=`<polyline fill="none" stroke="${palette.ai}" stroke-width="1.5" points="${values.map((v,i)=>v===null?'':`${x(i)},${ry(v)}`).filter(Boolean).join(' ')}"/>`;}
  out+='<g id="crosshairLayer" pointer-events="none"></g>';
  svg.innerHTML=out;
  $('drawingCount').textContent=lines().length+' drawings';
  $('chartFootnote').textContent=`${frame}m · IST · ${rows.length} bars${rows.some(r=>r.partial)?' · faded bars are partial aggregates':''}${prediction?(frame===5?' · Kronos scenario':' · Switch to 5m for Kronos overlay'):''}`;
  svg.setAttribute('aria-label',`${selected.symbol}, interactive ${frame}-minute ${chartMode} chart, ${rows.length} visible bars, ${lines().length} drawings. Use plus/minus to zoom, arrows to pan, Home to reset.`);
  readout(rows.at(-1),series.map(([data,color,name])=>`${name} ${fmt(data[end-1])}`).join('   '));
  if(hover)crosshair(hover);
 }
 function readout(row,extra=''){$('chartReadout').textContent=row?`${selected.symbol} · ${frame}m   ${row.timestamp.slice(5,16)}   O ${fmt(row.open)}   H ${fmt(row.high)}   L ${fmt(row.low)}   C ${fmt(row.close)}${row.partial?' · PARTIAL':''}   ${extra}`:'';}
 function coordinates(event){const box=svg.getBoundingClientRect();return {x:(event.clientX-box.left)/box.width*geometry.W,y:(event.clientY-box.top)/box.height*geometry.H};}
 function crosshair(p){if(!geometry)return;const g=geometry,i=Math.max(0,Math.min(g.rows.length-1,Math.floor((p.x-g.L)/g.step))),row=g.rows[i],xx=g.x(i),yy=Math.max(g.T,Math.min(g.priceBottom,p.y)),price=g.max-(yy-g.T)/(g.priceBottom-g.T)*(g.max-g.min);readout(row);const layer=$('crosshairLayer');if(layer)layer.innerHTML=`<line x1="${xx}" x2="${xx}" y1="${g.T}" y2="${g.bottom}" stroke="#748198" stroke-dasharray="3 3"/><line x1="${g.L}" x2="${g.W-g.R}" y1="${yy}" y2="${yy}" stroke="#748198" stroke-dasharray="3 3"/><rect x="${g.W-g.R}" y="${yy-9}" width="${g.R}" height="18" fill="#384357"/><text x="${g.W-g.R+6}" y="${yy+4}" fill="#fff" font-size="11">${fmt(price)}</text>`;}
 function point(p){const g=geometry,i=Math.max(0,Math.min(g.rows.length-1,Math.floor((p.x-g.L)/g.step)));return {stamp:g.rows[i].timestamp,price:g.max-(p.y-g.T)/(g.priceBottom-g.T)*(g.max-g.min)};}
 function zoom(factor){bars=Math.max(15,Math.min(600,Math.round(bars*factor)));hover=null;render();}
 svg.addEventListener('wheel',e=>{e.preventDefault();zoom(e.deltaY>0?1.15:1/1.15);},{passive:false});
 svg.addEventListener('pointerdown',e=>{if(!geometry||e.button!==0)return;const p=coordinates(e);if(p.y<geometry.T||p.y>geometry.priceBottom||p.x>geometry.W-geometry.R)return;svg.focus();
  if(tool!=='cursor'){const q=point(p);if(tool==='horizontal'){save([...lines(),{type:'horizontal',a:q}].slice(-100));}else if(!pending){pending=q;$('toolHint').textContent='Click the second point to finish the trend line';}else{save([...lines(),{type:'trend',a:pending,b:q}].slice(-100));pending=null;}render();return;}
  drag={x:p.x,offset};svg.setPointerCapture(e.pointerId);
 });
 svg.addEventListener('pointermove',e=>{if(!geometry)return;const p=coordinates(e);if(drag){offset=drag.offset+(p.x-drag.x)/geometry.step;hover=null;render();}else{hover=p;crosshair(p);}});
 svg.addEventListener('pointerup',()=>{drag=null;});svg.addEventListener('pointercancel',()=>{drag=null;});
 svg.addEventListener('pointerleave',()=>{hover=null;if($('crosshairLayer'))$('crosshairLayer').replaceChildren();});
 svg.addEventListener('keydown',e=>{if(['+','=','-','ArrowLeft','ArrowRight','Home','Escape'].includes(e.key))e.preventDefault();if(['+','='].includes(e.key))zoom(1/1.2);if(e.key==='-')zoom(1.2);if(e.key==='ArrowLeft'){offset+=10;render();}if(e.key==='ArrowRight'){offset-=10;render();}if(e.key==='Home'){offset=0;bars=90;render();}if(e.key==='Escape')setTool('cursor');});
 $('zoomIn').onclick=()=>zoom(1/1.2);$('zoomOut').onclick=()=>zoom(1.2);$('fitChart').onclick=()=>{bars=90;offset=0;hover=null;render();};
 $('undoDrawing').onclick=()=>{save(lines().slice(0,-1));pending=null;render();};$('clearDrawings').onclick=()=>{save([]);pending=null;render();};
 document.querySelectorAll('[data-tool]').forEach(b=>b.onclick=()=>setTool(b.dataset.tool));
 document.querySelectorAll('[data-frame]').forEach(b=>b.onclick=()=>{frame=Number(b.dataset.frame);document.querySelectorAll('[data-frame]').forEach(t=>{t.classList.toggle('selected',t===b);t.setAttribute('aria-pressed',String(t===b));});render();});
 for(const id of ['showSMA','showEMA','showVolume','showRSI'])$(id).onchange=render;
 document.querySelectorAll('[data-side]').forEach(b=>b.onclick=()=>{document.querySelectorAll('[data-side]').forEach(t=>{const active=t===b;t.classList.toggle('selected',active);t.setAttribute('aria-pressed',String(active));$('pane-'+t.dataset.side).hidden=!active;});});
 document.querySelectorAll('[data-dock]').forEach(b=>b.onclick=()=>{document.querySelectorAll('[data-dock]').forEach(t=>{const active=t===b;t.classList.toggle('selected',active);t.setAttribute('aria-pressed',String(active));$('dock-'+t.dataset.dock).hidden=!active;});});
 $('expandChart').onclick=()=>{document.body.classList.toggle('chart-expanded');$('expandChart').setAttribute('aria-label',document.body.classList.contains('chart-expanded')?'Restore workspace':'Expand chart');render();};
 window.renderWorkbench=render;
 new ResizeObserver(()=>requestAnimationFrame(render)).observe(svg);
 render();
})();
