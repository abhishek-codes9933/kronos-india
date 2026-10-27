import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch,Mock
import server
from trading import Terminal
from test_trading import ITEM

class TerminalAPITests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  for name,value in {'TERMINAL':Terminal(Path(self.tmp.name)/'db'),'CLIENT':'123','TOKEN':'test-token','CATALOGUE':{'NSE_EQ:1':ITEM}}.items():
   p=patch.object(server,name,value);p.start();self.addCleanup(p.stop)
 def ticket(self,mode='live'):
  return server.order_preview(dict(mode=mode,key='NSE_EQ:1',side='BUY',quantity=1,price=100,product='CNC'))
 def test_preview_does_not_submit(self):
  with patch.object(server,'dhan') as broker:
   p=self.ticket();self.assertEqual(p['mode'],'live');broker.assert_not_called()
 def test_explicit_confirmation_and_exact_payload(self):
  p=self.ticket()
  with self.assertRaises(ValueError):server.confirm_order({'id':p['id']})
  with patch.object(server,'dhan',return_value={'orderId':'123','orderStatus':'TRANSIT'}) as broker:
   server.confirm_order({'id':p['id'],'confirmed':True});server.confirm_order({'id':p['id'],'confirmed':True})
   self.assertEqual(broker.call_count,1)
   payload=broker.call_args.args[1];self.assertEqual(payload['orderType'],'LIMIT');self.assertEqual(payload['quantity'],1);self.assertEqual(payload['dhanClientId'],'123')
 def test_connection_changed(self):
  p=self.ticket()
  with patch.object(server,'TOKEN','another-token'),patch.object(server,'dhan') as broker:
   with self.assertRaises(ValueError):server.confirm_order({'id':p['id'],'confirmed':True})
   broker.assert_not_called()
 def test_stale_paper_quote_rejected(self):
  p=self.ticket('paper')
  with patch.object(server,'dhan',return_value={'data':{'NSE_EQ':{'1':{'last_price':99,'last_trade_time':'01/01/1980 00:00:00'}}}}):
   self.assertEqual(server.confirm_order({'id':p['id'],'confirmed':True})['status'],'REJECTED')
  self.assertEqual(server.TERMINAL.paper_book()['fills'],[])
 def test_list_broker_response(self):
  response=Mock(status_code=200,ok=True);response.json.return_value=[]
  with patch.object(server.requests,'request',return_value=response):self.assertEqual(server.dhan('orders'),[])
 def test_cancellation_requires_review(self):
  with patch.object(server,'dhan',return_value={'orderStatus':'PENDING','tradingSymbol':'TEST','transactionType':'BUY','remainingQuantity':1}) as broker:
   p=server.order_preview({'action':'cancel','order_id':'123'});self.assertEqual(broker.call_count,1)
   server.confirm_order({'id':p['id'],'confirmed':True});self.assertEqual(broker.call_args.kwargs['method'],'DELETE')

if __name__=='__main__':unittest.main()
