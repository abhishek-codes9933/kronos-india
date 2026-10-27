import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from trading import Terminal, validate_order

ITEM={'key':'NSE_EQ:1','id':'1','segment':'NSE_EQ','instrument':'EQUITY','symbol':'TEST','lot':'1','expiry':''}

class TradingTests(unittest.TestCase):
 def test_validation(self):
  for change in ({'quantity':0},{'quantity':1.5},{'price':'NaN'},{'side':'BAD'},{'product':'MTF'}):
   with self.assertRaises(ValueError):validate_order(ITEM,dict(quantity=1,price=100,side='BUY',product='CNC')|change)
  with self.assertRaises(ValueError):validate_order(ITEM|{'segment':'IDX_I'},dict(quantity=1,price=100,side='BUY',product='CNC'))
  with self.assertRaises(ValueError):validate_order(ITEM|{'segment':'NSE_FNO','lot':'25'},dict(quantity=1,price=100,side='BUY',product='MARGIN'))
 def test_confirm_once_and_account_binding(self):
  with tempfile.TemporaryDirectory() as d:
   t=Terminal(Path(d)/'orders.db'); p=t.preview('session',{'mode':'live','action':'place','payload':{}},'summary')
   with self.assertRaises(ValueError):t.confirm(p['id'],'other',lambda x:{})
   calls=[]
   def send(x):calls.append(x);return {'orderId':'test'}
   t.confirm(p['id'],'session',send);t.confirm(p['id'],'session',send)
   self.assertEqual(len(calls),1)
 def test_uncertain_submission_never_retried(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'orders.db';t=Terminal(path);p=t.preview('session',{'mode':'live'},'summary');calls=[]
   def fail(x):calls.append(x);raise TimeoutError()
   r=t.confirm(p['id'],'session',fail);self.assertEqual(r['status'],'UNKNOWN')
   Terminal(path).confirm(p['id'],'session',fail);self.assertEqual(len(calls),1)
 def test_expired_preview(self):
  with tempfile.TemporaryDirectory() as d:
   t=Terminal(Path(d)/'orders.db');p=t.preview('session',{},'x',ttl=-1)
   with self.assertRaises(ValueError):t.confirm(p['id'],'session',lambda x:{})
 def test_paper_cash_and_holdings(self):
  with tempfile.TemporaryDirectory() as d:
   t=Terminal(Path(d)/'orders.db');p=validate_order(ITEM,dict(quantity=2,price=110,side='BUY',product='CNC'))
   r={'payload':p,'symbol':'TEST'}
   self.assertEqual(t.paper_fill(r,115)['orderStatus'],'NOT_FILLED')
   t.paper_fill(r,100);self.assertEqual(t.paper_book()['cash'],999800)
   with self.assertRaises(ValueError):t.paper_fill({'payload':p|{'transactionType':'SELL','quantity':3,'price':90},'symbol':'TEST'},100)
   t.paper_fill({'payload':p|{'transactionType':'SELL','price':90},'symbol':'TEST'},105)
   self.assertEqual(t.paper_book()['cash'],1000010);self.assertEqual(t.paper_book()['positions'],[])
 def test_rejected_submission(self):
  with tempfile.TemporaryDirectory() as d:
   t=Terminal(Path(d)/'orders.db');p=t.preview('s',{},'x')
   def reject(r):raise ValueError('Broker rejected this order')
   self.assertEqual(t.confirm(p['id'],'s',reject)['status'],'REJECTED')
 def test_two_instances_cannot_submit_twice(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'orders.db';a=Terminal(path);b=Terminal(path);p=a.preview('s',{},'x');calls=[]
   def send(r):calls.append(1);return {'orderId':'test'}
   with ThreadPoolExecutor(2) as pool:
    jobs=[pool.submit(t.confirm,p['id'],'s',send) for t in (a,b)]
    for job in jobs:job.result()
   self.assertEqual(len(calls),1)

if __name__=='__main__':unittest.main()
