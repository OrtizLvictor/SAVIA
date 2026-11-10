"""SAVIA — API local. Launch with python iniciar.py."""
from __future__ import annotations
import json
import os
import re
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse
import requests
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from PIL import Image, UnidentifiedImageError
from . import database as db
from . import crops, vision, planning

ROOT=Path(__file__).resolve().parents[1]
FRONT=ROOT/'frontend'
DATA=ROOT/'datasets'
MAX_IMAGE=9*1024*1024
MAX_CSV=12*1024*1024

def require_text(value,name,maxlen=150):
    s=(value or '').strip()
    if not s:raise HTTPException(422,f'{name} es obligatorio.')
    if len(s)>maxlen:raise HTTPException(422,f'{name} supera {maxlen} caracteres.')
    return s

@asynccontextmanager
async def lifespan(app):
    db.init()
    # Bundled sample is identified by its actual name, and never presented as locally validated.
    if not crops.model_status():
        try:
            crops.train(DATA/'AgroIA_Zenodo_muestra_100_ES.csv')
            db.log('modelo','Modelo tabular inicializado','Muestra pública de 100 filas; evaluación exploratoria')
        except Exception as e:
            db.log('aviso','No se entrenó el modelo inicial',str(e)[:300])
    yield

app=FastAPI(title='SAVIA Studio',version='1.0.0',lifespan=lifespan,docs_url='/api/docs',redoc_url=None)
app.mount('/static',StaticFiles(directory=FRONT),name='static')
app.mount('/photos',StaticFiles(directory=db.STORE/'photos',check_dir=False),name='photos')

@app.get('/')
def index():return FileResponse(FRONT/'index.html')

class PlantInput(BaseModel):
    name:str=Field(min_length=1,max_length=120)
    species:str=Field(min_length=1,max_length=100)
    zone:str=Field(default='',max_length=100)
    planted_at:str=Field(default='',max_length=40)
    notes:str=Field(default='',max_length=1500)
class ReadingInput(BaseModel):
    plant_id:int|None=None
    temperature:float|None=None
    humidity:float|None=None
    soil_moisture:float|None=None
    light:float|None=None
    ph:float|None=None
    source:str='manual'
class PredictionInput(BaseModel):
    N:float; P:float; K:float; temperature:float; humidity:float; ph:float; rainfall:float
class RotationInput(PredictionInput):
    previous:str=""
    seasons:int=Field(default=4,ge=2,le=8)
    algorithm:str="recocido"

class AskInput(BaseModel):
    text:str=Field(min_length=1,max_length=1500)
    model:str|None=None

@app.get('/api/status')
def status():
    plants=db.rows('SELECT COUNT(*) total FROM plants')[0]['total']
    photos=db.rows('SELECT COUNT(*) total FROM photos')[0]['total']
    reads=db.rows('SELECT COUNT(*) total FROM readings')[0]['total']
    latest=db.rows('SELECT * FROM readings ORDER BY id DESC LIMIT 1')
    return {'app':'SAVIA','version':'1.0.0','plants':plants,'photos':photos,'readings':reads,
            'last_reading':latest[0] if latest else None,
            'crop_model':crops.model_status(),'vision_model':vision.status(),
            'datasets':[{'name':p.name,'size':p.stat().st_size} for p in sorted(DATA.glob('*.csv'))],
            'note':'Sin sensores conectados, los valores solo provienen de registros manuales; no hay datos simulados.'}

@app.get('/api/plants')
def plants():return db.rows('SELECT p.*, (SELECT COUNT(*) FROM photos WHERE plant_id=p.id) photo_count FROM plants p ORDER BY id DESC')

@app.post('/api/plants')
def create_plant(body:PlantInput):
    with db.connect() as c:
        cur=c.execute('INSERT INTO plants(name,species,zone,planted_at,notes) VALUES(?,?,?,?,?)',
             (require_text(body.name,'Nombre'),require_text(body.species,'Especie'),body.zone.strip(),body.planted_at.strip(),body.notes.strip()))
        pid=cur.lastrowid
    db.log('planta','Planta registrada',f'{body.name}, #{pid}')
    return {'ok':True,'id':pid}

@app.delete('/api/plants/{plant_id}')
def delete_plant(plant_id:int):
    rows=db.rows('SELECT * FROM plants WHERE id=?',(plant_id,))
    if not rows:raise HTTPException(404,'Planta no encontrada')
    files=db.rows('SELECT filename FROM photos WHERE plant_id=?',(plant_id,))
    with db.connect() as c:c.execute('DELETE FROM plants WHERE id=?',(plant_id,))
    for file in files:(db.STORE/'photos'/file['filename']).unlink(missing_ok=True)
    db.log('planta','Planta eliminada',rows[0]['name'])
    return {'ok':True}

@app.get('/api/readings')
def readings(plant_id:int|None=None,limit:int=100):
    limit=min(max(1,limit),300)
    if plant_id is None:return db.rows('SELECT * FROM readings ORDER BY id DESC LIMIT ?', (limit,))
    return db.rows('SELECT * FROM readings WHERE plant_id=? ORDER BY id DESC LIMIT ?',(plant_id,limit))

@app.post('/api/readings')
def add_reading(body:ReadingInput):
    if body.plant_id is not None and not db.rows('SELECT id FROM plants WHERE id=?',(body.plant_id,)):
        raise HTTPException(404,'Planta no encontrada')
    if all(getattr(body,k) is None for k in ['temperature','humidity','soil_moisture','light','ph']):
        raise HTTPException(422,'Introduce por lo menos una medición.')
    for k in ['humidity','soil_moisture']:
        v=getattr(body,k)
        if v is not None and not 0<=v<=100:raise HTTPException(422,f'{k}: debe estar en 0–100')
    if body.ph is not None and not 0<=body.ph<=14:raise HTTPException(422,'pH fuera de rango 0–14')
    # source is forced to manual to prevent fabricated sensor attribution through this route.
    with db.connect() as c:
        c.execute('INSERT INTO readings(plant_id,temperature,humidity,soil_moisture,light,ph,source) VALUES(?,?,?,?,?,?,?)',
        (body.plant_id,body.temperature,body.humidity,body.soil_moisture,body.light,body.ph,'manual'))
    db.log('sensor','Medición registrada','Captura manual')
    return {'ok':True}

@app.get('/api/photos')
def photos(plant_id:int|None=None):
    if plant_id is None:
        return db.rows('SELECT p.*,x.name plant_name FROM photos p JOIN plants x ON x.id=p.plant_id ORDER BY p.id DESC LIMIT 150')
    return db.rows('SELECT p.*,x.name plant_name FROM photos p JOIN plants x ON x.id=p.plant_id WHERE p.plant_id=? ORDER BY p.id DESC LIMIT 150',(plant_id,))

@app.post('/api/photos')
async def upload_photo(plant_id:int=Form(...),label:str=Form(''),note:str=Form(''),image:UploadFile=File(...)):
    if not db.rows('SELECT id FROM plants WHERE id=?',(plant_id,)):
        raise HTTPException(404,'Registra la planta antes de cargar fotos.')
    allowed={'image/jpeg','.jpg','image/png','.png','image/webp','.webp'}
    if image.content_type not in ('image/jpeg','image/png','image/webp'):
        raise HTTPException(415,'Solo JPEG, PNG o WEBP.')
    payload=await image.read(MAX_IMAGE+1)
    if not payload or len(payload)>MAX_IMAGE:raise HTTPException(413,'Imagen vacía o superior a 9 MB.')
    filename=uuid.uuid4().hex+'.jpg'
    target=db.STORE/'photos'/filename
    try:
        from io import BytesIO
        with Image.open(BytesIO(payload)) as im:
            im.verify()
        from PIL import ImageOps
        with Image.open(BytesIO(payload)) as im:
            frame=ImageOps.exif_transpose(im).convert('RGB')
            if frame.width*frame.height>45_000_000:raise HTTPException(413,'Resolución excesiva.')
            frame.thumbnail((2000,2000))
            frame.save(target,'JPEG',quality=88,optimize=True)
        visual=vision.metrics(target)
        classification=vision.classify(target)
        with db.connect() as c:
            c.execute('INSERT INTO photos(plant_id,filename,label,green_fraction,yellow_fraction,brown_fraction,sharpness,note) VALUES(?,?,?,?,?,?,?,?)',
                      (plant_id,filename,label.strip()[:100],visual['green_fraction'],visual['yellow_fraction'],visual['brown_fraction'],visual['sharpness'],note.strip()[:1000]))
        db.log('vision','Fotografía agregada',f'Planta #{plant_id}')
        return {'ok':True,'filename':filename,'metrics':visual,'assessment':classification}
    except HTTPException:
        target.unlink(missing_ok=True);raise
    except (UnidentifiedImageError,OSError,ValueError) as e:
        target.unlink(missing_ok=True)
        raise HTTPException(422,'La imagen no pudo abrirse o procesarse.') from e

@app.get('/api/datasets')
def datasets():
    return [{'name':p.name,'rows': max(0,sum(1 for _ in p.open(encoding='utf-8-sig'))-1),
             'training_ready': 'muestra_100_ES' in p.name or '5000_ES' in p.name,
             'url':'/api/datasets/'+p.name} for p in sorted(DATA.glob('*.csv'))]

@app.get('/api/datasets/{name}')
def dataset_download(name:str):
    if not re.fullmatch(r'[A-Za-z0-9_.-]+\.csv',name):raise HTTPException(400,'Nombre inválido')
    p=DATA/name
    if not p.is_file():raise HTTPException(404,'Archivo no disponible')
    return FileResponse(p,media_type='text/csv',filename=name)

@app.post('/api/datasets/upload')
async def dataset_upload(file:UploadFile=File(...)):
    if not file.filename or not file.filename.lower().endswith('.csv'):raise HTTPException(415,'Selecciona un .csv')
    raw=await file.read(MAX_CSV+1)
    if len(raw)>MAX_CSV or len(raw)==0:raise HTTPException(413,'CSV vacío o superior a 12 MB')
    # UTF-8 with BOM accepted. Validate before permanently saving.
    try:
        import pandas as pd
        from io import BytesIO
        df=pd.read_csv(BytesIO(raw),encoding='utf-8-sig')
        missing=[f for f in crops.FEATURES+['label'] if f not in df.columns]
        if missing:raise ValueError('Faltan columnas: '+', '.join(missing))
    except Exception as e:raise HTTPException(422,'CSV inválido: '+str(e)[:250]) from e
    name='importado_'+uuid.uuid4().hex[:10]+'.csv'
    (DATA/name).write_bytes(raw)
    db.log('dataset','CSV importado',name)
    return {'ok':True,'name':name,'rows':len(df)}

@app.post('/api/train/crops')
def train_crops(name:str='AgroIA_Zenodo_muestra_100_ES.csv'):
    if not re.fullmatch(r'[A-Za-z0-9_.-]+\.csv',name):raise HTTPException(400,'Nombre no permitido')
    path=DATA/name
    if not path.exists():raise HTTPException(404,'CSV no encontrado')
    try:
        result=crops.train(path)
        db.log('modelo','Clasificador de cultivos entrenado',str(result['rows'])+' filas / '+name)
        return result
    except (ValueError,KeyError) as e:raise HTTPException(422,str(e))

@app.post('/api/predict/crops')
def predict_crops(body:PredictionInput):
    try:return crops.predict(body.model_dump())
    except ValueError as e:raise HTTPException(422,str(e))

@app.post('/api/plan/rotation')
def plan_rotation(body:RotationInput):
    try:
        pred=crops.predict(body.model_dump())
        return planning.plan(pred['predictions'],body.previous.strip().lower(),body.seasons,body.algorithm)
    except ValueError as e:raise HTTPException(422,str(e))

@app.post('/api/train/vision')
def train_vision():
    try:
        result=vision.train();db.log('modelo','Clasificador visual entrenado',str(result['photos'])+' fotografías');return result
    except ValueError as e:raise HTTPException(422,str(e))

@app.get('/api/activity')
def activity():return db.rows('SELECT * FROM activity ORDER BY id DESC LIMIT 20')

@app.get('/api/weather')
def weather(latitude:float=24.81,longitude:float=-107.39):
    if not -90<=latitude<=90 or not -180<=longitude<=180:raise HTTPException(422,'Coordenadas inválidas')
    try:
        r=requests.get('https://api.open-meteo.com/v1/forecast',params={
            'latitude':latitude,'longitude':longitude,
            'current':'temperature_2m,relative_humidity_2m,precipitation',
            'daily':'temperature_2m_max,temperature_2m_min,precipitation_sum',
            'timezone':'auto','forecast_days':5},timeout=15)
        r.raise_for_status();v=r.json()
        if v.get('error'):raise ValueError(v.get('reason','Respuesta incorrecta'))
        return {'source':'Open-Meteo','coordinates':{'latitude':latitude,'longitude':longitude},
                'current':v.get('current'),'daily':v.get('daily'),
                'note':'Pronóstico regional, NO lectura de sensores en el invernadero.'}
    except (requests.RequestException,ValueError) as e:raise HTTPException(503,'No se pudo consultar Open-Meteo: '+str(e)[:250])

@app.get('/api/ollama')
def ollama_models():
    try:
        r=requests.get('http://127.0.0.1:11434/api/tags',timeout=3);r.raise_for_status()
        return {'online':True,'models':[m.get('name') for m in r.json().get('models',[]) if m.get('name')]}
    except (requests.RequestException,ValueError):return {'online':False,'models':[]}

@app.post('/api/assistant')
def assistant(body:AskInput):
    q=body.text.strip()
    crop=crops.model_status();vis=vision.status()
    context={'plantas':db.rows('SELECT id,name,species,zone FROM plants ORDER BY id DESC LIMIT 30'),
             'ultimas_mediciones':db.rows('SELECT * FROM readings ORDER BY id DESC LIMIT 8'),
             'modelo_cultivos':crop,'modelo_vision':vis}
    if body.model:
        info=ollama_models()
        if not info['online']:raise HTTPException(503,'Ollama no está ejecutándose. Inicia Ollama o usa el asistente local.')
        if body.model not in info['models']:raise HTTPException(422,'El modelo Ollama seleccionado no está instalado.')
        prompt=('Eres SAVIA, asistente de un prototipo de invernadero. Responde SIEMPRE en español, distingue hechos observados de inferencias. '
                'No inventes lecturas ni diagnostiques enfermedades con certeza. No recomiendes pesticidas ni fertilización específica sin validación. '
                'El contexto procede del registro local, puede ser parcial.\n'+json.dumps(context,ensure_ascii=False,default=str)[:5000]+'\nPregunta: '+q)
        try:
            r=requests.post('http://127.0.0.1:11434/api/generate',json={'model':body.model,'prompt':prompt,'stream':False},timeout=100)
            r.raise_for_status()
            return {'answer':r.json().get('response','Sin respuesta del modelo.'),'mode':'Ollama local; las respuestas requieren revisión'}
        except (requests.RequestException,ValueError) as e:raise HTTPException(503,'Error de Ollama: '+str(e)[:250])
    if re.search('enferm|plaga|mancha|amarill|infect|diagn',q,re.I):
        answer='SAVIA aún no dispone de un diagnóstico de enfermedades validado. Registra la planta y fotografías comparables; etiqueta imágenes verificadas por un especialista, entrena el modelo visual y confirma cualquier sospecha con agronomía. El color por sí solo no demuestra una enfermedad.'
    elif re.search('sensor|medici|humedad|temperatura|dato',q,re.I):
        latest=context['ultimas_mediciones']
        answer=('Hay '+str(len(latest))+' registros recientes. Último: '+json.dumps(latest[0],ensure_ascii=False) if latest else 'Aún no hay mediciones reales. Regístralas en Sensores; el sistema no inventa datos.')
    elif re.search('cultivo|entren|dataset|modelo',q,re.I):
        answer=('El clasificador tabular utiliza '+(str(crop['rows'])+' filas del archivo '+crop['source'] if crop else 'ningún CSV entrenado')+'. Sirve para recomendaciones exploratorias de cultivos con N,P,K,temperatura,humedad,pH y precipitación; no reconoce enfermedades en fotografías.')
    else:
        answer=f'Actualmente hay {len(context["plantas"])} plantas registradas. Puedes agregar plantas, capturar fotos, registrar mediciones, entrenar un CSV y consultar el pronóstico regional. Para conversación generativa conecta Ollama opcional. No cuento con datos de campo fuera de los registrados.'
    return {'answer':answer,'mode':'Asistente local basado en reglas y datos, no LLM'}
