import unittest
from unittest.mock import patch,Mock
import server
from core import now_ist
class AdapterTests(unittest.TestCase):
 def setUp(self):
  server.load_catalogue();server.HISTORY.clear();server.QUOTE_CACHE.clear()
 def test_offline_history(self):
  h=server.get_history('IDX_I:13','sample')
  self.assertGreaterEqual(len(h['rows']),400)
  self.assertEqual(h['source'],'sample')
 def test_dhan_missing_candles_rejected(self):
  with patch.object(server,'dhan',return_value={'timestamp':[1],'open':[]}):
   with self.assertRaisesRegex(ValueError,'incomplete'):server.get_history('IDX_I:13','dhan')
 def test_invalid_candles_rejected(self):
  with patch.object(server,'dhan',return_value={'timestamp':[1700000000],'open':[100],'high':[90],'low':[80],'close':[95],'volume':[0]}):
   with self.assertRaisesRegex(ValueError,'bounds'):server.get_history('IDX_I:13','dhan')
 def test_expired_token_message(self):
  response=Mock(status_code=401)
  with patch.object(server.requests,'request',return_value=response):
   with self.assertRaisesRegex(ValueError,'rejected access'):server.dhan('profile',credentials=('123','not-a-real-token'))
 def test_quote_batch_mapping(self):
  with patch.object(server,'dhan',return_value={'data':{'IDX_I':{'13':{'last_price':110,'ohlc':{'close':100}}}}}):
   q=server.get_quotes(['IDX_I:13'])['quotes']['IDX_I:13']
   self.assertAlmostEqual(q['change_percent'],10)
 def test_catalogue_has_core_segments(self):
  segments={v['segment'] for v in server.CATALOGUE.values()}
  self.assertTrue({'IDX_I','NSE_EQ','BSE_EQ','NSE_FNO','BSE_FNO','MCX_COMM'}.issubset(segments))
 def test_indices_not_filtered_by_placeholder_expiry(self):
  self.assertGreater(sum(x['segment']=='IDX_I' for x in server.CATALOGUE.values()),100)
 def test_host_and_origin_checks(self):
  handler=object.__new__(server.Handler)
  handler.headers={'Host':'evil.example'}
  self.assertFalse(handler.allowed())
  handler.headers={'Host':f'127.0.0.1:{server.PORT}','Origin':'https://evil.example'}
  self.assertFalse(handler.allowed())
  handler.headers={'Host':f'127.0.0.1:{server.PORT}'}
  self.assertFalse(handler.allowed(True))
  handler.headers['X-Kronos-Token']=server.NONCE
  self.assertTrue(handler.allowed(True))
if __name__=='__main__':unittest.main()
