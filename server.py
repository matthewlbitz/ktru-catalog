#!/usr/bin/env python3
"""Read-only KTRU catalog. Python standard library; no installation required."""
import argparse, json, os, re, sqlite3, threading, unicodedata
from pathlib import Path
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
ROOT = Path(__file__).resolve().parent

def normalized(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(value or '')).casefold() if not unicodedata.combining(c))
def natural(value):
    return tuple((1, int(s)) if s.isdigit() else (0, s) for s in re.split(r'(\d+)', normalized(value)))
def text(value):
    return str(value).strip() if value is not None else ''
def genres(value):
    return [s.strip() for s in text(value).replace('Folk, World, & Country', 'Folk / World / Country').split(',') if s.strip()]
def tracks(value):
    try:
        value = json.loads(value) if isinstance(value, str) else value
        return [dict(title=text(t.get('title')), duration=text(t.get('duration')), position=text(t.get('position'))) for t in (value or []) if isinstance(t, dict)]
    except (ValueError, TypeError): return []

class Catalog:
    def __init__(self, path):
        self.path = Path(path).expanduser().resolve()
        self.lock = threading.Lock()
        self.stamp = None
        self.refresh()
    def refresh(self):
        stamp = tuple((p.stat().st_mtime_ns, p.stat().st_size) if p.exists() else None for p in [self.path, Path(str(self.path)+'-wal')])
        with self.lock:
            if self.stamp == stamp: return
            with sqlite3.connect(self.path.as_uri()+'?mode=ro', uri=True) as db:
                db.row_factory = sqlite3.Row
                db.execute('PRAGMA query_only=ON')
                columns = {r[1] for r in db.execute('PRAGMA table_info(rainbow_albums)')}
                if not {'id','artist','title','barcode'} <= columns:
                    raise ValueError('Expected rainbow_albums with id, artist, title, and barcode columns.')
                source = db.execute("SELECT * FROM rainbow_albums WHERE barcode IS NOT NULL AND trim(CAST(barcode AS TEXT)) != ''").fetchall()
            records = []
            for row in source:
                r = dict(row)
                shelf = text(r.get('final_shelf')) or text(r.get('new_shelf')) or text(r.get('new_shelf_label')) or text(r.get('shelf_label'))
                explicit = text(r.get('format') or r.get('media_format') or r.get('medium'))
                media = 'Vinyl' if ('vinyl' in explicit.lower() or explicit.upper() in ('LP','12"','7"') or shelf.upper().startswith('V.')) else ('CD' if not explicit or 'cd' in explicit.lower() else explicit)
                record = dict(id=r['id'], title=text(r.get('title')) or 'Untitled', artist=text(r.get('artist')) or 'Unknown artist', artist_sort=text(r.get('artist_sort')) or text(r.get('artist')), year=int(r.get('year') or 0), genre=text(r.get('primary_genre')) or text(r.get('genre')), secondary_genre=text(r.get('secondary_genre')), style=text(r.get('style')), shelf=shelf, barcode=text(r.get('barcode')), format=media, cover_image=text(r.get('cover_image')), discogs_id=text(r.get('discogs_id')), discogs_link=text(r.get('discogs_link')), label=text(r.get('label')), catalog_number=text(r.get('catalog_number')), original_shelf=text(r.get('shelf_label')), tracklist=tracks(r.get('tracklist')))
                records.append(record)
            records.sort(key=lambda r:(natural(r['shelf']), natural(r['artist_sort']), natural(r['title']), r['year'], natural(r['barcode']), r['id']))
            positions = {}
            for r in records:
                shelf = r['shelf']
                positions[shelf] = positions.get(shelf, 0)+1
                r['shelf_position'] = positions[shelf] if shelf else None
                r['organizational_id'] = f"{shelf}.{positions[shelf]}" if shelf else ''
                r['_search'] = normalized(' '.join(text(r.get(k)) for k in ['artist','title','genre','secondary_genre','style','shelf','barcode','organizational_id','discogs_id','label','catalog_number']))
            self.records = records
            self.by_id = {str(r['id']):r for r in records}
            self.meta = dict(total=len(records), genres=sorted({g for r in records for g in genres(r['genre'])}), secondary_genres=sorted({g for r in records for g in genres(r['secondary_genre'])}), shelves=sorted({r['shelf'] for r in records if r['shelf']}, key=natural), formats=sorted({r['format'] for r in records}))
            self.stamp = stamp
    def search(self, q):
        rows = self.records
        for term in normalized(q.get('q','')).split(): rows = [r for r in rows if term in r['_search']]
        for key in ['artist','title']:
            term = normalized(q.get(key,''))
            if term: rows = [r for r in rows if term in normalized(r[key])]
        for key in ['genre','secondary_genre']:
            if q.get(key): rows = [r for r in rows if normalized(q[key]) in [normalized(g) for g in genres(r[key])]]
        for key in ['format','shelf']:
            if q.get(key): rows = [r for r in rows if normalized(r[key]) == normalized(q[key].strip())]
        if q.get('year_from'): rows = [r for r in rows if r['year'] >= int(q['year_from'])]
        if q.get('year_to'): rows = [r for r in rows if r['year'] and r['year'] <= int(q['year_to'])]
        sort = q.get('sort','artist')
        if sort == 'year_desc': rows = sorted(rows,key=lambda r:(-r['year'],natural(r['artist_sort']),natural(r['title'])))
        elif sort == 'year_asc': rows = sorted(rows,key=lambda r:(r['year'] or 99999,natural(r['artist_sort']),natural(r['title'])))
        elif sort == 'title': rows = sorted(rows,key=lambda r:(natural(r['title']),natural(r['artist_sort'])))
        elif sort != 'shelf': rows = sorted(rows,key=lambda r:(natural(r['artist_sort']),natural(r['title'])))
        page = max(1, int(q.get('page',1))); size=40
        total = len(rows); pages=max(1,(total+size-1)//size); page=min(page,pages)
        return dict(total=total,page=page,pages=pages,records=[public(r,False) for r in rows[(page-1)*size:page*size]])
def public(r, full=True):
    return {k:v for k,v in r.items() if not k.startswith('_') and (full or k!='tracklist')}

class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kw): super().__init__(*args,directory=str(ROOT/'public'),**kw)
    def do_GET(self):
        p=urlparse(self.path)
        if not p.path.startswith('/api/'):
            if p.path not in ('/','/index.html','/app.js','/style.css','/icon.svg'): return self.send_error(404)
            return super().do_GET()
        try:
            catalog.refresh()
            q={k:v[0] for k,v in parse_qs(p.query).items()}
            if p.path=='/api/meta': return self.reply(catalog.meta)
            if p.path=='/api/albums': return self.reply(catalog.search(q))
            if p.path.startswith('/api/albums/'):
                r=catalog.by_id.get(p.path.rsplit('/',1)[1])
                return self.reply(public(r) if r else {'error':'Album not found'},200 if r else 404)
            return self.reply({'error':'Not found'},404)
        except (ValueError,TypeError): return self.reply({'error':'Check your year range and search values.'},400)
        except (sqlite3.Error,OSError): return self.reply({'error':'The catalog is temporarily unavailable. Check the database path and retry.'},503)
    def reply(self,data,status=200):
        payload=json.dumps(data,ensure_ascii=False).encode()
        self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(payload)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(payload)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description='KTRU read-only record library')
    parser.add_argument('--db',default=os.environ.get('DB_PATH',str(ROOT.parent/'data/masterAlbums.db')))
    parser.add_argument('--port',type=int,default=3004)
    args=parser.parse_args()
    if not Path(args.db).is_file(): parser.error('Database not found. Put this app inside KTRU beside data/, or use --db /path/to/masterAlbums.db')
    catalog=Catalog(args.db)
    print(f'KTRU · {len(catalog.records):,} barcoded records\nhttp://localhost:{args.port}\nDatabase: {catalog.path}\nRead only. Ctrl+C to stop.',flush=True)
    try: ThreadingHTTPServer(('127.0.0.1',args.port),Handler).serve_forever()
    except KeyboardInterrupt: print('\nLibrary closed.')
