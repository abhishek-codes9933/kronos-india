from datetime import datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))

def now_ist():
    return datetime.now(IST).replace(tzinfo=None)

def segment_for(exchange, segment, instrument):
    if instrument == 'INDEX':
        return 'IDX_I'
    return {('NSE','E'):'NSE_EQ', ('BSE','E'):'BSE_EQ',
            ('NSE','D'):'NSE_FNO', ('BSE','D'):'BSE_FNO',
            ('NSE','C'):'NSE_CURRENCY', ('BSE','C'):'BSE_CURRENCY',
            ('MCX','M'):'MCX_COMM'}.get((exchange,segment))

def safe_instrument(key, catalogue):
    if key not in catalogue:
        raise ValueError('Choose an instrument from the catalogue.')
    return catalogue[key]

def completed_candles(rows, now=None):
    now = now or now_ist()
    return [r for r in rows if datetime.fromisoformat(r['timestamp']) + timedelta(minutes=5) <= now]

def future_slots(last, count, segment):
    # Approximate weekday sessions, explicitly disclosed in the interface.
    opening = (9,15) if segment in ('NSE_EQ','BSE_EQ','NSE_FNO','BSE_FNO','IDX_I') else (9,0)
    closing = (15,30) if opening == (9,15) else ((17,0) if 'CURRENCY' in segment else (23,30))
    result=[]
    current=last
    while len(result)<count:
        current += timedelta(minutes=5)
        if current.weekday()>=5 or (current.hour,current.minute)>=closing:
            current=(current+timedelta(days=1)).replace(hour=opening[0],minute=opening[1],second=0)
            while current.weekday()>=5:
                current+=timedelta(days=1)
        if (current.hour,current.minute)<opening:
            current=current.replace(hour=opening[0],minute=opening[1],second=0)
        result.append(current)
    return result
