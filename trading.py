"""Explicit preview/confirm order flow. No inference path can submit an order."""
import json
import secrets
import sqlite3
import threading
import time
from contextlib import contextmanager
from decimal import Decimal, InvalidOperation
from core import now_ist

def validate_order(item, body):
    if item['segment'] not in ('NSE_EQ','BSE_EQ','NSE_FNO','BSE_FNO'):
        raise ValueError('Order tickets support NSE/BSE cash and F&O. Indices are not directly tradable; currency and commodity orders are not enabled.')
    if item.get('expiry') and item['expiry'][:10]<str(now_ist().date()):
        raise ValueError('This contract has expired. Refresh the catalogue.')
    side=body.get('side');product=body.get('product')
    if side not in ('BUY','SELL'):raise ValueError('Choose Buy or Sell.')
    cash=item['segment'] in ('NSE_EQ','BSE_EQ')
    if product not in (('CNC','INTRADAY') if cash else ('MARGIN','INTRADAY')):
        raise ValueError('Choose a product supported for this segment.')
    try:
        qty=Decimal(str(body.get('quantity')));price=Decimal(str(body.get('price')))
        lot=Decimal(str(item.get('lot') or '1'))
        if not qty.is_finite() or qty!=qty.to_integral_value() or not 0<qty<=1000000:raise ValueError('Quantity must be a positive whole number, at most 1,000,000.')
        if not price.is_finite() or not 0<price<=10000000:raise ValueError('Enter a valid positive limit price.')
        if not lot.is_finite() or lot<1 or qty%lot:raise ValueError('Quantity must be a multiple of the catalogue lot size.')
    except InvalidOperation:raise ValueError('Enter valid quantity and price.') from None
    return {'transactionType':side,'exchangeSegment':item['segment'],'productType':product,
            'orderType':'LIMIT','validity':'DAY','securityId':item['id'],'quantity':int(qty),
            'price':float(price),'afterMarketOrder':False}

class Terminal:
    def __init__(self,path):
        self.path=path;path.parent.mkdir(parents=True,exist_ok=True);self.lock=threading.Lock()
        with self.db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS intents (id TEXT PRIMARY KEY, session TEXT, expires REAL, request TEXT, summary TEXT, status TEXT, result TEXT)')
            db.execute('CREATE TABLE IF NOT EXISTS paper_fills (id TEXT PRIMARY KEY, symbol TEXT, security TEXT, side TEXT, quantity INTEGER, price REAL, stamp TEXT)')
    @contextmanager
    def db(self):
        db=sqlite3.connect(self.path,timeout=10)
        try:
            with db:yield db
        finally:db.close()
    def preview(self,session,request,summary,ttl=60):
        ident=secrets.token_hex(12)
        with self.db() as db:
            db.execute('INSERT INTO intents VALUES(?,?,?,?,?,?,?)',(ident,session,time.time()+ttl,json.dumps(request),summary,'PREVIEW','{}'))
        return {'id':ident,'summary':summary,'expires_in':ttl,'mode':request.get('mode')}
    def confirm(self,ident,session,send):
        with self.lock:
            with self.db() as db:
                db.execute('BEGIN IMMEDIATE')
                row=db.execute('SELECT session,expires,request,status,result FROM intents WHERE id=?',(ident,)).fetchone()
                if not row or row[0]!=session:raise ValueError('Preview belongs to another connection. Review again.')
                if row[3]!='PREVIEW':return {'status':row[3],'result':json.loads(row[4]),'id':ident}
                if row[1]<time.time():raise ValueError('Preview expired. Review the order again.')
                db.execute("UPDATE intents SET status='SUBMITTING' WHERE id=?",(ident,))
            # Persist SUBMITTING before any external call. A crash/timeout cannot silently retry.
            try:
                result=send(json.loads(row[2]));status='SUBMITTED'
            except ValueError as e:
                status='REJECTED';result={'message':str(e)}
            except Exception:
                status='UNKNOWN';result={'message':'Submission outcome is uncertain. Refresh the broker order book and match the correlation ID before creating another order. Never retry blindly.'}
            with self.db() as db:db.execute('UPDATE intents SET status=?,result=? WHERE id=?',(status,json.dumps(result),ident))
            return {'status':status,'result':result,'id':ident}
    def journal(self,session):
        with self.db() as db:
            return [{'id':r[0],'summary':r[1],'status':r[2],'result':json.loads(r[3])} for r in db.execute("SELECT id,summary,status,result FROM intents WHERE session=? AND status!='PREVIEW' ORDER BY rowid DESC LIMIT 50",(session,))]
    def paper_fill(self,request,price):
        p=request['payload'];key=p['exchangeSegment']+':'+p['securityId']
        if p['exchangeSegment'] not in ('NSE_EQ','BSE_EQ') or p['productType']!='CNC':raise ValueError('Paper simulation supports cash delivery only.')
        if (p['transactionType']=='BUY' and price>p['price']) or (p['transactionType']=='SELL' and price<p['price']):
            return {'paper':True,'orderStatus':'NOT_FILLED','message':'Limit not reached at the fresh snapshot. No pending paper order was created.'}
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            cash=1000000-db.execute("SELECT COALESCE(SUM(CASE WHEN side='BUY' THEN quantity*price ELSE -quantity*price END),0) FROM paper_fills").fetchone()[0]
            quantity=db.execute("SELECT COALESCE(SUM(CASE WHEN side='BUY' THEN quantity ELSE -quantity END),0) FROM paper_fills WHERE security=?",(key,)).fetchone()[0]
            if p['transactionType']=='BUY' and p['quantity']*price>cash:raise ValueError('Insufficient virtual cash.')
            if p['transactionType']=='SELL' and p['quantity']>quantity:raise ValueError('Paper selling requires an existing virtual holding.')
            ident=secrets.token_hex(8)
            db.execute('INSERT INTO paper_fills VALUES(?,?,?,?,?,?,?)',(ident,request['symbol'],key,p['transactionType'],p['quantity'],price,now_ist().isoformat(timespec='seconds')))
        return {'paper':True,'orderId':ident,'orderStatus':'SIMULATED_FILL','price':price}
    def paper_book(self):
        with self.db() as db:
            fills=[dict(zip(('id','symbol','key','side','quantity','price','time'),r)) for r in db.execute('SELECT * FROM paper_fills ORDER BY rowid DESC LIMIT 100')]
            cash=1000000-db.execute("SELECT COALESCE(SUM(CASE WHEN side='BUY' THEN quantity*price ELSE -quantity*price END),0) FROM paper_fills").fetchone()[0]
            positions=[{'symbol':r[0],'key':r[1],'quantity':r[2]} for r in db.execute("SELECT symbol,security,SUM(CASE WHEN side='BUY' THEN quantity ELSE -quantity END) FROM paper_fills GROUP BY security HAVING SUM(CASE WHEN side='BUY' THEN quantity ELSE -quantity END)!=0")]
        return {'cash':cash,'fills':fills,'positions':positions}
