'use strict';
let previewId=null,ticketKey='',bookSequence=0,lastTechnical=null;
function syncTicket(){
 if(ticketKey!==selected.key){
  ticketKey=selected.key;$('tradePrice').value='';$('tradeQty').value=Number(selected.lot)||1;
  $('ticketInstrument').textContent=(selected.name||selected.symbol)+' · '+selected.segment;
  $('ticketRules').textContent=`Lot size: ${selected.lot||'—'} units${selected.expiry?' · Expiry '+selected.expiry:''}. Indices cannot be traded directly.`;
  $('tradeProduct').value=selected.segment.endsWith('_FNO')?'MARGIN':'CNC';
 }
 $('reviewOrder').textContent=$('tradeMode').value==='live'?'Review REAL order':'Review paper order';
 $('ticketForm').classList.toggle('real-ticket',$('tradeMode').value==='live');
 const value=Number($('tradeQty').value)*Number($('tradePrice').value);
 $('ticketValue').textContent=Number.isFinite(value)&&value>0?`Order value ₹${fmt(value)} before charges${value>50000?' · exceeds ₹50,000':''}`:'';
 if(history!==lastTechnical){
  lastTechnical=history;
  if(!history){$('technicalSummary').textContent='Load candle history to view trend and volatility.';return;}
  const rows=history.rows,close=rows.at(-1).close;
  const mean=n=>rows.slice(-n).reduce((a,r)=>a+r.close,0)/Math.min(n,rows.length);
  const recent=rows.slice(-15),tr=recent.slice(1).map((r,i)=>Math.max(r.high-r.low,Math.abs(r.high-recent[i].close),Math.abs(r.low-recent[i].close)));
  const atr=tr.reduce((a,b)=>a+b,0)/tr.length;
  $('technicalSummary').textContent=`Close ₹${fmt(close)} · SMA 20 ₹${fmt(mean(20))} · SMA 50 ₹${fmt(mean(50))} · 14-bar average true range ₹${fmt(atr)}. These describe completed candles; they are not model confidence or trade instructions.`;
 }
}
function table(target,title,columns,rows,action){
 const el=$(target);el.replaceChildren();const t=document.createElement('table'),caption=document.createElement('caption');caption.textContent=title;t.append(caption);
 const head=document.createElement('tr');for(const [label] of columns){const th=document.createElement('th');th.textContent=label;head.append(th);}if(action){const th=document.createElement('th');th.textContent='Action';head.append(th);}t.append(head);
 for(const row of rows){const tr=document.createElement('tr');for(const [,key] of columns){const td=document.createElement('td');td.textContent=String(row[key]??'—');tr.append(td);}if(action){const td=document.createElement('td');action(td,row);tr.append(td);}t.append(tr);}el.append(t);
 if(!rows.length){const p=document.createElement('p');p.className='small muted';p.textContent='No entries.';el.append(p);}
}
async function refreshBook(){
 const mode=$('tradeMode').value,seq=++bookSequence;$('refreshBook').disabled=true;$('bookStatus').textContent='Loading…';
 try{const d=await api(mode==='paper'?'/api/paper':'/api/terminal');if(seq!==bookSequence||mode!==$('tradeMode').value)return;
 if(mode==='paper'){
  $('bookStatus').textContent=`Virtual cash ₹${fmt(d.cash)} · local simulation · fees and slippage excluded`;
  table('orderBook','Paper fills',[['Time','time'],['Symbol','symbol'],['Side','side'],['Units','quantity'],['Fill price','price']],d.fills);
  table('positionBook','Paper holdings',[['Symbol','symbol'],['Units','quantity']],d.positions);$('submissionJournal').replaceChildren();
 }else{
  $('bookStatus').textContent='Dhan snapshot · refreshed '+new Date().toLocaleTimeString()+' · Refresh after every action. An acknowledgement is not a fill.';
  table('orderBook','Real Dhan orders',[['Order ID','orderId'],['Symbol','tradingSymbol'],['Side','transactionType'],['Qty','quantity'],['Price','price'],['Status','orderStatus']],d.orders,(td,r)=>{
   if(['PENDING','TRANSIT','PART_TRADED'].includes(r.orderStatus)){const b=document.createElement('button');b.className='secondary';b.textContent='Review cancel';b.onclick=()=>review({action:'cancel',order_id:r.orderId});td.append(b);}
  });
  table('positionBook','Real Dhan positions',[['Symbol','tradingSymbol'],['Product','productType'],['Net units','netQty'],['Realized P&L','realizedProfit'],['Unrealized P&L','unrealizedProfit']],d.positions);
  table('submissionJournal','Submission journal (this connection)',[['Review','summary'],['State','status']],d.journal);
 }
 }catch(e){$('bookStatus').textContent=e.message;}finally{if(seq===bookSequence)$('refreshBook').disabled=false;}
}
async function review(body){
 previewId=null;$('reviewOrder').disabled=true;$('tradeMessage').textContent='Preparing review…';
 try{const p=await api('/api/order/preview',body);previewId=p.id;
  $('orderSummary').textContent=p.summary.split(' | ').join('\n')+'\n\nReview expires in 60 seconds.';
  $('orderReviewTitle').textContent=p.mode==='live'?'Review REAL action':'Review paper order';
  $('confirmOrder').textContent=p.mode==='live'?'Confirm REAL action':'Confirm paper order';
  $('orderAcknowledge').checked=false;$('confirmOrder').disabled=true;$('orderError').textContent='';$('orderDialog').showModal();$('tradeMessage').textContent='';
 }catch(e){$('tradeMessage').textContent=e.message;}finally{$('reviewOrder').disabled=false;}
}
$('ticketForm').onsubmit=e=>{e.preventDefault();review({mode:$('tradeMode').value,key:selected.key,side:$('tradeSide').value,product:$('tradeProduct').value,quantity:$('tradeQty').value,price:$('tradePrice').value});};
$('dismissOrder').onclick=()=>{$('orderDialog').close();previewId=null;};
$('orderAcknowledge').onchange=()=>{$('confirmOrder').disabled=!$('orderAcknowledge').checked||!previewId;};
$('confirmOrder').onclick=async()=>{
 if(!previewId||!$('orderAcknowledge').checked)return;const id=previewId;previewId=null;$('confirmOrder').disabled=true;
 try{const r=await api('/api/order/confirm',{id,confirmed:true});$('orderDialog').close();$('tradeMessage').textContent=r.status+' · '+JSON.stringify(r.result);refreshBook();}
 catch(e){$('orderError').textContent=e.message+' Check the broker order book before trying another order.';}
};
$('useQuote').onclick=()=>{const q=quotes[selected.key];if(!connected||!q||!Number.isFinite(q.price)){$('tradeMessage').textContent='Connect Dhan and wait for a quote.';return;}$('tradePrice').value=q.price;syncTicket();};
$('tradeMode').onchange=()=>{$('orderBook').replaceChildren();$('positionBook').replaceChildren();$('submissionJournal').replaceChildren();syncTicket();refreshBook();};
$('refreshBook').onclick=refreshBook;$('tradeQty').oninput=syncTicket;$('tradePrice').oninput=syncTicket;
setInterval(syncTicket,500);syncTicket();refreshBook();
