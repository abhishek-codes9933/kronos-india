"""Download the public security master with validated, bounded range requests."""
import csv
import io
from concurrent.futures import ThreadPoolExecutor
import requests

URL='https://images.dhan.co/api-data/api-scrip-master-detailed.csv'

def download(destination):
    with requests.get(URL,headers={'Range':'bytes=0-0'},stream=True,timeout=(10,30)) as response:
        response.raise_for_status()
        content_range=response.headers.get('Content-Range','')
        etag=response.headers.get('ETag')
        if response.status_code!=206 or '/' not in content_range:
            raise ValueError('Catalogue server did not support a verified download. Try later.')
        size=int(content_range.split('/')[-1])
    if not 1000<size<250_000_000:raise ValueError('Unexpected catalogue size.')
    block=2*1024*1024
    starts=list(range(0,size,block))
    def fetch(start):
        end=min(size-1,start+block-1)
        headers={'Range':f'bytes={start}-{end}'}
        if etag:headers['If-Range']=etag
        for attempt in range(3):
            try:
                r=requests.get(URL,headers=headers,timeout=(10,45))
                if r.status_code!=206 or r.headers.get('Content-Range')!=f'bytes {start}-{end}/{size}' or len(r.content)!=end-start+1:
                    raise ValueError('Catalogue changed during download. Please retry.')
                return r.content
            except requests.RequestException:
                if attempt==2:raise
    with ThreadPoolExecutor(max_workers=6) as pool:
        content=b''.join(pool.map(fetch,starts))
    rows=list(csv.DictReader(io.StringIO(content.decode('utf-8-sig'))))
    if not {'NSE','BSE','MCX'}.issubset({r.get('EXCH_ID') for r in rows}) or not all(r.get('TICK_SIZE') is not None for r in rows):
        raise ValueError('Catalogue was incomplete. The previous file has been retained.')
    temporary=destination.with_suffix('.tmp')
    temporary.write_bytes(content)
    temporary.replace(destination)
