"""Smoke tests. Use a disposable installation: API tests write to local storage."""
from io import BytesIO
from PIL import Image
from fastapi.testclient import TestClient
from backend.app import app

def test_local_workflow():
    with TestClient(app) as c:
        assert c.get('/').status_code == 200
        assert c.get('/api/status').status_code == 200
        datasets=c.get('/api/datasets').json()
        assert any(x['name']=='AgroIA_Zenodo_muestra_100_ES.csv' and x['rows']==100 for x in datasets)
        status=c.get('/api/status').json()
        assert status['crop_model'] and status['crop_model']['rows']==100
        bad=c.post('/api/train/vision')
        assert bad.status_code==422
        created=c.post('/api/plants',json={'name':'Prueba API','species':'tomate'})
        assert created.status_code==200
        pid=created.json()['id']
        reading=c.post('/api/readings',json={'plant_id':pid,'temperature':25,'humidity':59})
        assert reading.status_code==200
        assert any(x['plant_id']==pid for x in c.get('/api/readings').json())
        buf=BytesIO();Image.new('RGB',(40,40),(30,130,45)).save(buf,format='PNG');buf.seek(0)
        upload=c.post('/api/photos',data={'plant_id':str(pid),'note':'Foto sintética usada SOLO en test'},
                      files={'image':('test.png',buf,'image/png')})
        assert upload.status_code==200,upload.text
        assert upload.json()['assessment']['status']=='sin_modelo'
        assert any(x['plant_id']==pid for x in c.get('/api/photos').json())
        assert c.delete(f'/api/plants/{pid}').status_code==200
        assert all(x['id']!=pid for x in c.get('/api/plants').json())
        inp={'N':40,'P':27,'K':45,'temperature':21.66,'humidity':94.79,'ph':5.89,'rainfall':112.43}
        assert len(c.post('/api/predict/crops',json=inp).json()['predictions'])>0
        seq=c.post('/api/plan/rotation',json={**inp,'algorithm':'tabu','seasons':4})
        assert seq.status_code==200 and len(seq.json()['plan'])==4
