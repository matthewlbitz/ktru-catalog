import importlib.util, sqlite3, tempfile, unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('catalog_server',Path(__file__).resolve().parents[1]/'server.py')
s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)
class CatalogTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'masterAlbums.db'
  with sqlite3.connect(self.path) as c:
   c.execute('CREATE TABLE rainbow_albums(id INTEGER PRIMARY KEY,artist TEXT,title TEXT,barcode TEXT,final_shelf TEXT,artist_sort TEXT,year INTEGER,primary_genre TEXT,secondary_genre TEXT,tracklist TEXT)')
   c.executemany('INSERT INTO rainbow_albums VALUES(?,?,?,?,?,?,?,?,?,?)',[(1,'The Zebra','Second','001','14D','Zebra',2001,'Rock','Pop','[{"title":"One","duration":"3:14"}]'),(2,'Álpha','First','002','14D','Alpha',1999,'Rock','Jazz','[]'),(3,'Aardvark','Excluded',None,'14D',None,2000,'Rock','Jazz','[]'),(4,'Blank','Excluded','  ','14D',None,2000,'Rock','Jazz','[]'),(5,'Beta','Third','003','15A',None,2005,'Jazz','Pop','bad json')])
  self.before=self.path.read_bytes();self.cat=s.Catalog(self.path)
 def tearDown(self):self.temp.cleanup()
 def test_only_barcoded_and_stable_positions(self):
  self.assertEqual(self.cat.meta['total'],3)
  self.assertNotIn('3',self.cat.by_id)
  self.assertEqual(self.cat.by_id['2']['organizational_id'],'14D.1')
  r=self.cat.search({'artist':'zebra','sort':'year_desc'})['records'][0]
  self.assertEqual(r['organizational_id'],'14D.2')
 def test_combined_filters_and_inclusive_years(self):
  q=dict(artist='alpha',title='first',genre='Rock',secondary_genre='Jazz',year_from='1999',year_to='1999',shelf='14d',format='CD')
  self.assertEqual(self.cat.search(q)['total'],1)
  q['year_from']='2000';self.assertEqual(self.cat.search(q)['total'],0)
 def test_readonly_and_tracks(self):
  self.assertEqual(self.before,self.path.read_bytes())
  self.assertEqual(self.cat.by_id['1']['tracklist'][0]['duration'],'3:14')
  self.assertEqual(self.cat.by_id['5']['tracklist'],[])
 def test_refresh(self):
  with sqlite3.connect(self.path) as c:c.execute("UPDATE rainbow_albums SET barcode='004' WHERE id=3")
  self.cat.refresh();self.assertEqual(self.cat.meta['total'],4)
  self.assertEqual(self.cat.by_id['3']['organizational_id'],'14D.1')
 def test_pagination_and_formats(self):
  self.assertEqual(self.cat.search({'page':'999'})['page'],1)
  self.assertEqual(self.cat.search({'format':'Vinyl'})['total'],0)
if __name__=='__main__':unittest.main()
