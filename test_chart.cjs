const assert=require('node:assert/strict');
const {aggregateCandles,sma,ema,rsi}=require('./static/chart-math.js');
const rows=Array.from({length:15},(_,i)=>({timestamp:`2026-10-26 09:${String(15+i*5%45).padStart(2,'0')}:00`,open:i+10,high:i+12,low:i+9,close:i+11,volume:100}));
const input=[
 {timestamp:'2026-10-26 09:15:00',open:10,high:12,low:9,close:11,volume:100},
 {timestamp:'2026-10-26 09:20:00',open:11,high:14,low:10,close:13,volume:200},
 {timestamp:'2026-10-26 09:25:00',open:13,high:15,low:12,close:14,volume:300},
 {timestamp:'2026-10-26 09:30:00',open:14,high:16,low:13,close:15,volume:100},
 {timestamp:'2026-10-27 09:15:00',open:20,high:22,low:19,close:21,volume:100}];
const a=aggregateCandles(input,15,15);
assert.equal(a.length,3);assert.deepEqual([a[0].open,a[0].high,a[0].low,a[0].close,a[0].volume],[10,15,9,14,600]);
assert.equal(a[0].partial,false);assert.equal(a[1].partial,true);assert.equal(a[2].timestamp,'2026-10-27 09:15:00');
assert.equal(aggregateCandles(input,5,15).length,5);
assert.deepEqual(sma([1,2,3,4],3),[null,null,2,3]);
assert.deepEqual(ema([1,2,3,4],3),[null,null,2,3]);
assert.equal(rsi(Array.from({length:20},(_,i)=>i+1),14).at(-1),100);
assert.equal(rsi(Array(20).fill(10),14).at(-1),50);
assert.equal(rsi(Array.from({length:20},(_,i)=>20-i),14).at(-1),0);
console.log('Chart aggregation and indicator checks passed');
