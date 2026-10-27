import unittest
from datetime import datetime,timedelta
from core import segment_for, completed_candles, future_slots, safe_instrument
class CoreTests(unittest.TestCase):
 def test_segments(self):
  for ex,seg,kind,want in [('NSE','E','EQUITY','NSE_EQ'),('BSE','D','OPTIDX','BSE_FNO'),('MCX','M','FUTCOM','MCX_COMM'),('NSE','C','FUTCUR','NSE_CURRENCY'),('NSE','I','INDEX','IDX_I')]:
   self.assertEqual(segment_for(ex,seg,kind),want)
 def test_incomplete(self):
  now=datetime(2026,10,23,10,3)
  rows=[{'timestamp':'2026-10-23 09:55:00'},{'timestamp':'2026-10-23 10:00:00'}]
  self.assertEqual(len(completed_candles(rows,now)),1)
 def test_weekend(self):
  slots=future_slots(datetime(2026,10,23,15,25),2,'NSE_EQ')
  self.assertEqual(slots[0],datetime(2026,10,26,9,15))
 def test_allowlist(self):
  with self.assertRaises(ValueError):safe_instrument('NSE_EQ:../etc',{})
if __name__=='__main__':unittest.main()
