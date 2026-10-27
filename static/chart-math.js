'use strict';
function aggregateCandles(rows,minutes,anchor=15){
 const groups=new Map();
 for(const r of rows){
  const minute=Number(r.timestamp.slice(11,13))*60+Number(r.timestamp.slice(14,16));
  const slot=Math.floor((minute-anchor)/minutes)*minutes+anchor;
  const stamp=r.timestamp.slice(0,10)+' '+String(Math.floor(slot/60)).padStart(2,'0')+':'+String(slot%60).padStart(2,'0')+':00';
  if(!groups.has(stamp))groups.set(stamp,{...r,timestamp:stamp,volume:Number(r.volume)||0,count:1});
  else{const g=groups.get(stamp);g.high=Math.max(g.high,r.high);g.low=Math.min(g.low,r.low);g.close=r.close;g.volume+=Number(r.volume)||0;g.count++;}
 }
 return [...groups.values()].map(r=>({...r,partial:r.count<minutes/5}));
}
function sma(values,n){let sum=0;return values.map((v,i)=>{sum+=v;if(i>=n)sum-=values[i-n];return i>=n-1?sum/n:null;});}
function ema(values,n){let current=null;const base=sma(values,n);return values.map((v,i)=>{if(i<n-1)return null;current=current===null?base[i]:v*2/(n+1)+current*(1-2/(n+1));return current;});}
function rsi(values,n=14){
 const out=values.map(()=>null);let gain=0,loss=0;
 for(let i=1;i<values.length;i++){const delta=values[i]-values[i-1],g=Math.max(delta,0),l=Math.max(-delta,0);
  if(i<=n){gain+=g/n;loss+=l/n;}else{gain=(gain*(n-1)+g)/n;loss=(loss*(n-1)+l)/n;}
  if(i>=n)out[i]=gain===0&&loss===0?50:loss===0?100:100-100/(1+gain/loss);
 }return out;
}
if(typeof module!=='undefined')module.exports={aggregateCandles,sma,ema,rsi};
