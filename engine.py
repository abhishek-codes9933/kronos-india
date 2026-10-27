"""Local Kronos inference. Imported lazily so the app opens immediately."""
import os
import sys
import threading
import time
import hashlib
import json
import copy
from collections import OrderedDict
from pathlib import Path
from core import future_slots

BASE=Path(__file__).resolve().parent
WORK=BASE.parent.parent/'work'
KRONOS=Path(os.environ.get('KRONOS_HOME',r'C:\Users\abhis\Documents\Kronos'))
EXPERIMENT=BASE.parent/'nifty_training'/'best_model'
_models={}
_lock=threading.Lock()
_results=OrderedDict()

def forecast(rows, instrument, choice, horizon, speed='balanced'):
    started=time.perf_counter()
    import numpy as np
    import pandas as pd
    import torch
    os.environ['HF_HOME']=str(WORK/'hf_cache')
    os.environ['HF_HUB_OFFLINE']='1'
    sys.path.insert(0,str(KRONOS))
    from model import Kronos,KronosTokenizer,KronosPredictor
    if choice not in ('original','nifty'):
        raise ValueError('Unknown model.')
    if choice=='nifty' and instrument['key']!='IDX_I:13':
        raise ValueError('The Nifty-trained model is available only for Nifty 50.')
    if len(rows)<400:
        raise ValueError('At least 400 completed five-minute candles are needed.')
    if horizon not in (6,12,24):
        raise ValueError('Choose 6, 12 or 24 forecast candles.')
    if speed not in ('fast','balanced'):raise ValueError('Unknown forecast mode.')
    paths=1 if speed=='fast' else 3
    signature=hashlib.sha256(json.dumps([rows[-400:],instrument,choice,horizon,speed],sort_keys=True,allow_nan=False).encode()).hexdigest()
    with _lock:
        if signature in _results:
            result=copy.deepcopy(_results[signature]);_results.move_to_end(signature)
            result.update(cache_hit=True,elapsed_seconds=round(time.perf_counter()-started,3))
            return result
        torch.set_num_threads(4)
        torch.manual_seed(42);np.random.seed(42)
        device='cuda:0' if torch.cuda.is_available() else 'cpu'
        if choice not in _models:
            tokenizer=KronosTokenizer.from_pretrained('NeoQuasar/Kronos-Tokenizer-base')
            model=Kronos.from_pretrained(str(EXPERIMENT) if choice=='nifty' else 'NeoQuasar/Kronos-small')
            _models[choice]=KronosPredictor(model,tokenizer,device=device,max_context=512)
        df=pd.DataFrame(rows[-400:])
        times=pd.to_datetime(df.timestamp)
        slots=pd.Series(future_slots(times.iloc[-1].to_pydatetime(),horizon,instrument['segment']))
        expiry=instrument.get('expiry')
        if expiry and slots.iloc[-1].date()>pd.Timestamp(expiry).date():
            raise ValueError('This horizon extends beyond contract expiry. Choose a shorter horizon or a later-expiry contract.')
        cols=['open','high','low','close']
        if instrument['instrument']!='INDEX' and 'volume' in df:
            cols+=['volume']
        prediction=_models[choice].predict(df[cols],times,slots,horizon,sample_count=paths,verbose=False)
        if not np.isfinite(prediction.to_numpy()).all():
            raise ValueError('Model returned invalid numbers. Try another instrument.')
        data=[]
        for i,(_,p) in enumerate(prediction.iterrows()):
            data.append({'timestamp':str(slots.iloc[i]),**{c:float(p[c]) for c in ['open','high','low','close']}})
        result={'rows':data,'device':device,'model':choice,'as_of':rows[-1]['timestamp'],
                'input_candles':400,'paths':paths,'speed':speed,'instrument':instrument,
                'cache_hit':False,'elapsed_seconds':round(time.perf_counter()-started,3),
                'calendar_note':'Projected weekday trading slots. Holidays, special sessions and MCX seasonal closing changes are not modeled.'}
        _results[signature]=copy.deepcopy(result)
        while len(_results)>16:_results.popitem(last=False)
        return result
