import csv
import io
import json
import math
import os
import secrets
import hashlib
import threading
import time
import webbrowser
from datetime import datetime,timedelta
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse,parse_qs
import requests
from core import IST,now_ist,segment_for,safe_instrument,completed_candles
from trading import Terminal,validate_order

BASE=Path(__file__).resolve().parent
PORT=int(os.environ.get('KRONOS_PORT','8765'))
ORIGIN=f'http://127.0.0.1:{PORT}'
NONCE=secrets.token_urlsafe(32)
KRONOS=Path(os.environ.get('KRONOS_HOME',r'C:\Users\abhis\Documents\Kronos'))
CATALOGUE={}
CATALOGUE_LOCK=threading.Lock()
CREDENTIAL_LOCK=threading.Lock()
QUOTE_LOCK=threading.Lock()
HISTORY_LOCK=threading.Lock()
JOB_LOCK=threading.Lock()
DOWNLOAD_LOCK=threading.Lock()
CLIENT=''
TOKEN=''
PROFILE={}
GENERATION=0
HISTORY={}
QUOTE_CACHE={}
JOB={'status':'idle'}
LAST_QUOTE=0
TERMINAL=Terminal(BASE/'data/terminal.sqlite3')

def load_catalogue():
    result={}
    path=BASE/'data/instruments.csv'
    if path.exists():
        with path.open(encoding='utf-8-sig',newline='') as f:
            for r in csv.DictReader(f):
                segment=segment_for(r.get('EXCH_ID'),r.get('SEGMENT'),r.get('INSTRUMENT'))
                sid=r.get('SECURITY_ID','')
                if not segment or not sid.isdigit():continue
                if r.get('TICK_SIZE') is None:continue
                expiry=r.get('SM_EXPIRY_DATE') or ''
                if r['INSTRUMENT']!='INDEX' and expiry and expiry not in ('NA','nan'):
                    try:
                        if datetime.fromisoformat(expiry[:10]).date()<now_ist().date():continue
                    except ValueError:continue
                key=f'{segment}:{sid}'
                symbol=r.get('SYMBOL_NAME') or r.get('DISPLAY_NAME') or sid
                result[key]={'key':key,'id':sid,'segment':segment,'exchange':r.get('EXCH_ID',''),
                    'symbol':symbol,'name':r.get('DISPLAY_NAME') or symbol,'instrument':r['INSTRUMENT'],
                    'expiry':expiry if r['INSTRUMENT']!='INDEX' and expiry not in ('NA','nan') else '',
                    'strike':r.get('STRIKE_PRICE') or '','option':r.get('OPTION_TYPE') or '',
                    'lot':r.get('LOT_SIZE') or '','search':f"{symbol} {r.get('DISPLAY_NAME','')} {r.get('UNDERLYING_SYMBOL','')}".upper()}
    for sid,symbol in [('13','NIFTY 50'),('25','NIFTY BANK'),('27','NIFTY FIN SERVICE'),('51','SENSEX')]:
        key=f'IDX_I:{sid}'
        result.setdefault(key,{'key':key,'id':sid,'segment':'IDX_I','exchange':'INDEX','symbol':symbol,'name':symbol,'instrument':'INDEX','expiry':'','strike':'','option':'','lot':'','search':symbol})
    with CATALOGUE_LOCK:
        CATALOGUE.clear();CATALOGUE.update(result)

def public_instrument(item):return {k:v for k,v in item.items() if k!='search'}

def dhan(path,payload=None,credentials=None,method=None):
    if credentials is None:
        with CREDENTIAL_LOCK:credentials=(CLIENT,TOKEN)
    client,token=credentials
    if not token:raise ValueError('Connect your Dhan account first.')
    try:
        r=requests.request(method or ('GET' if payload is None else 'POST'),'https://api.dhan.co/v2/'+path,
            headers={'access-token':token,'client-id':client},json=payload,timeout=(8,30))
    except requests.RequestException:
        if path.startswith('orders') and (payload is not None or method=='DELETE'):
            raise RuntimeError('Uncertain broker submission') from None
        raise ValueError('Dhan could not be reached. Check your internet connection and retry.') from None
    if r.status_code in (401,403):raise ValueError('Dhan rejected access. Check your token and Data API subscription.')
    if r.status_code==429:raise ValueError('Dhan rate limit reached. Wait a few seconds and retry.')
    if not r.ok:
        if r.status_code>=500 and path.startswith('orders'):raise RuntimeError('Uncertain broker response')
        raise ValueError(f'Dhan returned HTTP {r.status_code}. Check order details and account access.')
    try:data=r.json()
    except ValueError:raise RuntimeError('Dhan returned an unreadable response.') from None
    if isinstance(data,dict) and (data.get('status')=='failure' or data.get('errorCode')):
        code=str(data.get('errorCode','unknown'))[:30]
        raise ValueError(f'Dhan could not return this data (code {code}). Check instrument availability and account access.')
    return data

def trading_session():
    return hashlib.sha256((CLIENT+':'+TOKEN).encode()).hexdigest()

def order_preview(body):
    with CREDENTIAL_LOCK:
        if not TOKEN:raise ValueError('Connect Dhan before preparing a ticket.')
        session=trading_session()
        if body.get('action')=='cancel':
            ident=str(body.get('order_id',''))
            if not ident.isdigit():raise ValueError('Invalid broker order ID.')
            order=dhan('orders/'+ident,credentials=(CLIENT,TOKEN))
            if order.get('orderStatus') not in ('PENDING','TRANSIT','PART_TRADED'):raise ValueError('Only an open order can be cancelled.')
            summary=f"CANCEL REAL ORDER {ident} | {order.get('tradingSymbol','')} | {order.get('transactionType','')} | remaining {order.get('remainingQuantity','check broker')}"
            return TERMINAL.preview(session,{'mode':'live','action':'cancel','order_id':ident},summary)
        mode=body.get('mode')
        if mode not in ('paper','live'):raise ValueError('Choose Paper or Real trading.')
        item=safe_instrument(body.get('key'),CATALOGUE);payload=validate_order(item,body)
        if mode=='paper' and (item['segment'] not in ('NSE_EQ','BSE_EQ') or payload['productType']!='CNC'):
            raise ValueError('Paper simulation supports NSE/BSE cash delivery only. Choose CNC.')
        correlation=secrets.token_hex(12);payload['correlationId']=correlation
        value=payload['quantity']*payload['price']
        summary=f"{mode.upper()} | {payload['transactionType']} {payload['quantity']} units of {item['symbol']} ({item['segment']}, ID {item['id']}) | LIMIT Rs {payload['price']:.4f} | {payload['productType']} | DAY | value Rs {value:,.2f} (excludes charges) | lot {item.get('lot')} | reference {correlation}"
        if value>50000:summary+=' | CAUTION: order value exceeds Rs 50,000.'
        if mode=='live':summary+=' | Real money. Dhan requires a whitelisted static IP. Broker validates tick size, limits, margin and permissions.'
        else:summary+=' | Virtual cash only; snapshot fill simulation, no fees or slippage, no pending paper orders.'
        return TERMINAL.preview(session,{'mode':mode,'action':'place','payload':payload,'symbol':item['symbol'],'key':item['key']},summary)

def confirm_order(body):
    if body.get('confirmed') is not True:raise ValueError('Explicit confirmation is required.')
    # Serialize connection changes with submission; never use another account's token.
    with CREDENTIAL_LOCK:
        if not TOKEN:raise ValueError('Reconnect Dhan and review again.')
        credentials=(CLIENT,TOKEN)
        def submit(request):
            if request['mode']=='paper':
                global LAST_QUOTE
                p=request['payload']
                with QUOTE_LOCK:
                    delay=1.1-(time.monotonic()-LAST_QUOTE)
                    if delay>0:time.sleep(delay)
                    LAST_QUOTE=time.monotonic()
                    data=dhan('marketfeed/quote',{p['exchangeSegment']:[int(p['securityId'])]},credentials=credentials)
                q=data.get('data',{}).get(p['exchangeSegment'],{}).get(p['securityId'],{})
                try:stamp=datetime.strptime(q['last_trade_time'],'%d/%m/%Y %H:%M:%S')
                except (KeyError,ValueError,TypeError):raise ValueError('A fresh exchange trade timestamp is required for a paper fill.')
                if not 0<=(now_ist()-stamp).total_seconds()<=60:raise ValueError('No recent trade. Paper fills are disabled while quotes are stale or the market is closed.')
                price=q.get('last_price')
                if not isinstance(price,(int,float)) or not math.isfinite(price) or price<=0:raise ValueError('Invalid quote.')
                return TERMINAL.paper_fill(request,price)
            if request['action']=='cancel':return dhan('orders/'+request['order_id'],credentials=credentials,method='DELETE')
            result=dhan('orders',request['payload']|{'dhanClientId':CLIENT},credentials=credentials)
            if not isinstance(result,dict) or not result.get('orderId'):raise RuntimeError('Missing broker acknowledgement')
            return result
        return TERMINAL.confirm(str(body.get('id','')),trading_session(),submit)

def get_history(key,source):
    item=safe_instrument(key,CATALOGUE)
    if source not in ('dhan','sample'):raise ValueError('Unknown data source.')
    cache_key=(key,source,GENERATION)
    with HISTORY_LOCK:
        cached=HISTORY.get(cache_key)
        if cached and time.monotonic()-cached[0]<55:return cached[1]
        if source=='sample':
            if key!='IDX_I:13':raise ValueError('Offline history is available for Nifty 50 only. Connect Dhan for other instruments.')
            paths=sorted((KRONOS/'outputs').glob('nifty_5min_training_*.csv'))
            path=paths[-1] if paths else KRONOS/'outputs/nifty_5min.csv'
            if not path.exists():raise ValueError('No offline Nifty file found. Connect Dhan to load market data.')
            with path.open(encoding='utf-8-sig') as f:
                raw=list(csv.DictReader(f))[-600:]
            rows=[{'timestamp':r['timestamps'],**{k:float(r[k]) for k in ('open','high','low','close')},'volume':float(r.get('volume',0))} for r in raw]
        else:
            end=now_ist();start=end-timedelta(days=45)
            data=dhan('charts/intraday',{'securityId':item['id'],'exchangeSegment':item['segment'],
                'instrument':item['instrument'],'interval':'5','oi':False,
                'fromDate':start.strftime('%Y-%m-%d %H:%M:%S'),'toDate':end.strftime('%Y-%m-%d %H:%M:%S')})
            timestamps=data.get('timestamp',[])
            if not timestamps:raise ValueError('No recent candles for this instrument. Try another contract or check your Dhan access.')
            if any(len(data.get(k,[]))!=len(timestamps) for k in ('open','high','low','close')):
                raise ValueError('Dhan returned incomplete candle data.')
            rows=[]
            for i,stamp in enumerate(timestamps):
                row={'timestamp':datetime.fromtimestamp(int(stamp),IST).strftime('%Y-%m-%d %H:%M:%S')}
                row.update({k:float(data[k][i]) for k in ('open','high','low','close')})
                row['volume']=float(data.get('volume',[0]*len(timestamps))[i])
                rows.append(row)
        rows=sorted({r['timestamp']:r for r in rows}.values(),key=lambda r:r['timestamp'])
        rows=completed_candles(rows)
        if not rows:raise ValueError('No completed candles available yet.')
        for r in rows:
            if not all(math.isfinite(r[k]) for k in ('open','high','low','close','volume')):raise ValueError('Invalid candle values received.')
            if r['high']+.02<max(r['open'],r['close'],r['low']) or r['low']-.02>min(r['open'],r['close'],r['high']):raise ValueError('Candle price bounds failed validation.')
        result={'instrument':public_instrument(item),'rows':rows[-600:],'source':source,'as_of':rows[-1]['timestamp'],
                'received_at':now_ist().isoformat(timespec='seconds'),'completed_only':True}
        HISTORY[cache_key]=(time.monotonic(),result)
        return result

def get_quotes(keys):
    global LAST_QUOTE
    if len(keys)>30:raise ValueError('Watchlist supports up to 30 instruments.')
    instruments=[safe_instrument(k,CATALOGUE) for k in keys]
    with CREDENTIAL_LOCK:
        credentials=(CLIENT,TOKEN);signature=(tuple(sorted(keys)),GENERATION)
    with QUOTE_LOCK:
        cached=QUOTE_CACHE.get(signature)
        if cached and time.monotonic()-cached[0]<4:return cached[1]
        delay=1.1-(time.monotonic()-LAST_QUOTE)
        if delay>0:time.sleep(delay)
        payload={}
        for item in instruments:payload.setdefault(item['segment'],[]).append(int(item['id']))
        LAST_QUOTE=time.monotonic()
        data=dhan('marketfeed/ohlc',payload,credentials=credentials).get('data',{})
        quotes={}
        for item in instruments:
            q=data.get(item['segment'],{}).get(item['id'],{})
            price=q.get('last_price');previous=q.get('ohlc',{}).get('close')
            quotes[item['key']]={'price':price,'previous_close':previous,
                'change_percent':((price/previous-1)*100 if price is not None and previous else None)}
        result={'quotes':quotes,'received_at':now_ist().isoformat(timespec='seconds'),
                'note':'Latest Dhan snapshot. Receipt time is not the exchange trade timestamp.'}
        QUOTE_CACHE[signature]=(time.monotonic(),result)
        return result

def run_forecast(key,source,model,horizon,job_id,speed='balanced'):
    global JOB
    try:
        history=get_history(key,source)
        from engine import forecast
        result=forecast(history['rows'],history['instrument'],model,horizon,speed)
        result.update(source=source,generated_at=now_ist().isoformat(timespec='seconds'),job_id=job_id)
        with JOB_LOCK:JOB={'status':'complete','result':result,'id':job_id,'key':key}
    except Exception as e:
        message=str(e) if isinstance(e,ValueError) else 'Forecast failed. Check that the Kronos model files and Python environment are available.'
        with JOB_LOCK:JOB={'status':'error','error':message,'id':job_id,'key':key}

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def send(self,status,data,kind='application/json'):
        body=json.dumps(data,allow_nan=False).encode() if kind=='application/json' else data.encode() if isinstance(data,str) else data
        self.send_response(status)
        for k,v in {'Content-Type':kind+'; charset=utf-8','Content-Length':str(len(body)),
                    'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','X-Frame-Options':'DENY',
                    'Referrer-Policy':'no-referrer','Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"}.items():self.send_header(k,v)
        self.end_headers();self.wfile.write(body)
    def allowed(self,mutation=False):
        if self.headers.get('Host')!=f'127.0.0.1:{PORT}':return False
        if self.headers.get('Origin') not in (None,ORIGIN):return False
        if mutation and self.headers.get('X-Kronos-Token')!=NONCE:return False
        return True
    def do_GET(self):
        if not self.allowed():return self.send(403,{'error':'Local access only.'})
        path=urlparse(self.path);query=parse_qs(path.query)
        try:
            if path.path=='/':
                return self.send(200,(BASE/'static/index.html').read_text(encoding='utf-8').replace('__NONCE__',NONCE),'text/html')
            if path.path in ('/app.js','/terminal.js','/chart-math.js','/workbench.js','/style.css'):
                return self.send(200,(BASE/'static'/path.path[1:]).read_text(encoding='utf-8'),'text/javascript' if path.path.endswith('js') else 'text/css')
            if path.path=='/api/status':
                return self.send(200,{'connected':bool(TOKEN),'profile':PROFILE,'instruments':len(CATALOGUE),
                    'catalogue_date':datetime.fromtimestamp((BASE/'data/instruments.csv').stat().st_mtime,IST).isoformat() if (BASE/'data/instruments.csv').exists() else None,
                    'now':now_ist().isoformat(timespec='seconds'),'nifty_model':(BASE.parent/'nifty_training/best_model/config.json').exists()})
            if path.path=='/api/search':
                q=query.get('q',[''])[0].upper()[:100];segment=query.get('segment',['all'])[0]
                tokens=q.split();matches=[]
                with CATALOGUE_LOCK:
                    for v in CATALOGUE.values():
                        if segment!='all' and v['segment']!=segment:continue
                        if all(t in v['search'] for t in tokens):matches.append(v)
                matches.sort(key=lambda x:(x['instrument']!='INDEX',x['instrument']!='EQUITY',len(x['symbol']),x['symbol'],x['expiry']))
                return self.send(200,{'items':[public_instrument(v) for v in matches[:60]],'total':len(matches)})
            if path.path=='/api/history':return self.send(200,get_history(query.get('key',['IDX_I:13'])[0],query.get('source',['sample'])[0]))
            if path.path=='/api/quotes':return self.send(200,get_quotes(query.get('keys',['IDX_I:13'])[0].split(',')))
            if path.path=='/api/job':
                with JOB_LOCK:return self.send(200,JOB)
            if path.path=='/api/paper':return self.send(200,TERMINAL.paper_book())
            if path.path=='/api/terminal':
                with CREDENTIAL_LOCK:
                    if not TOKEN:raise ValueError('Connect Dhan to view your order book.')
                    credentials=(CLIENT,TOKEN);session=trading_session()
                return self.send(200,{'orders':dhan('orders',credentials=credentials),'positions':dhan('positions',credentials=credentials),'journal':TERMINAL.journal(session)})
            return self.send(404,{'error':'Not found.'})
        except ValueError as e:return self.send(400,{'error':str(e)})
        except Exception:return self.send(500,{'error':'Unable to complete the request. Please retry.'})
    def do_POST(self):
        global CLIENT,TOKEN,PROFILE,GENERATION,JOB
        if not self.allowed(True):return self.send(403,{'error':'Invalid local session. Reload the app.'})
        try:
            size=int(self.headers.get('Content-Length','0'))
            if not 0<size<=16000:raise ValueError('Invalid request size.')
            body=json.loads(self.rfile.read(size))
            if not isinstance(body,dict):raise ValueError('Invalid request.')
            if self.path=='/api/connect':
                client=str(body.get('client','')).strip();token=str(body.get('token','')).strip()
                if not client.isdigit() or not 20<len(token)<12000:raise ValueError('Enter your Dhan client ID and access token.')
                profile=dhan('profile',credentials=(client,token))
                if str(profile.get('dhanClientId',''))!=client:raise ValueError('The token belongs to a different client ID.')
                if str(profile.get('dataPlan','')).lower()!='active':raise ValueError('Your Dhan Data API plan is not active.')
                with CREDENTIAL_LOCK:
                    CLIENT,TOKEN=client,token;PROFILE={k:profile.get(k) for k in ('dataPlan','tokenValidity')};GENERATION+=1
                return self.send(200,{'connected':True,'profile':PROFILE})
            if self.path=='/api/disconnect':
                with CREDENTIAL_LOCK:CLIENT='';TOKEN='';PROFILE={};GENERATION+=1
                return self.send(200,{'connected':False})
            if self.path=='/api/forecast':
                key=body.get('key');safe_instrument(key,CATALOGUE)
                source=body.get('source','dhan');model=body.get('model','original');horizon=int(body.get('horizon',12))
                if source not in ('dhan','sample') or model not in ('original','nifty') or horizon not in (6,12,24):raise ValueError('Invalid forecast settings.')
                if model=='nifty' and key!='IDX_I:13':raise ValueError('Nifty model is only available for Nifty 50.')
                speed=body.get('speed','balanced')
                if speed not in ('fast','balanced'):raise ValueError('Invalid speed mode.')
                with JOB_LOCK:
                    if JOB['status']=='running':return self.send(409,{'error':'A forecast is already running. Please wait.'})
                    jid=secrets.token_hex(8);JOB={'status':'running','key':key,'id':jid}
                threading.Thread(target=run_forecast,args=(key,source,model,horizon,jid,speed),daemon=True).start()
                return self.send(202,{'id':jid,'status':'running'})
            if self.path=='/api/order/preview':return self.send(200,order_preview(body))
            if self.path=='/api/order/confirm':return self.send(200,confirm_order(body))
            if self.path=='/api/catalogue':
                if not DOWNLOAD_LOCK.acquire(blocking=False):return self.send(409,{'error':'The catalogue is already refreshing.'})
                try:
                    from catalogue import download
                    download(BASE/'data/instruments.csv');load_catalogue()
                except requests.RequestException:raise ValueError('Could not refresh the public catalogue. Try again later.') from None
                finally:DOWNLOAD_LOCK.release()
                return self.send(200,{'instruments':len(CATALOGUE)})
            return self.send(404,{'error':'Not found.'})
        except (ValueError,TypeError) as e:return self.send(400,{'error':str(e)})
        except Exception:return self.send(500,{'error':'Unable to complete the request. Please retry.'})

if __name__=='__main__':
    load_catalogue()
    print(f'Kronos India: {ORIGIN} | {len(CATALOGUE)} instruments',flush=True)
    try:
        server=ThreadingHTTPServer(('127.0.0.1',PORT),Handler)
    except OSError:
        print('Port is already in use. If Kronos India is running, open '+ORIGIN,flush=True)
        raise SystemExit(1)
    if '--no-browser' not in __import__('sys').argv:threading.Timer(1,lambda:webbrowser.open(ORIGIN)).start()
    server.serve_forever()
