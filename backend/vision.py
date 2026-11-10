"""Visual features for longitudinal tracking and explicitly supervised exploratory classifiers.
Color fractions are NOT plant health diagnoses and are affected by lighting/background.
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import joblib
from PIL import Image, ImageOps, ImageFilter
from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier
from sklearn.model_selection import GroupShuffleSplit
from sklearn.metrics import accuracy_score
from . import database as db

ROOT=Path(__file__).resolve().parents[1]
PHOTO_DIR=ROOT/'storage/photos'
VMODEL=ROOT/'storage/models/vision.joblib'
VMETA=ROOT/'storage/models/vision_meta.json'

def metrics(file:Path):
    with Image.open(file) as im:
        a=np.asarray(ImageOps.exif_transpose(im).convert('RGB').resize((256,256)),dtype=np.float32)/255.0
    r,g,b=a[:,:,0],a[:,:,1],a[:,:,2]
    # Simple color descriptions, NOT disease probabilities.
    green=(g>r*1.15)&(g>b*1.12)&(g>0.18)
    yellow=(r>0.28)&(g>0.25)&(b<g*.76)&(np.abs(r-g)<.27)
    brown=(r>g*1.18)&(g>b*1.06)&(r>.16)&(r<.79)
    lum=.299*r+.587*g+.114*b
    gx=np.diff(lum,axis=1); gy=np.diff(lum,axis=0)
    sharp=float((gx*gx).mean()+(gy*gy).mean()) 
    return {'green_fraction':round(float(green.mean()),4),'yellow_fraction':round(float(yellow.mean()),4),
            'brown_fraction':round(float(brown.mean()),4),'sharpness':round(sharp,6)}

def feature_vector(file:Path):
    with Image.open(file) as im:
        a=np.asarray(ImageOps.exif_transpose(im).convert('RGB').resize((128,128)),dtype=np.uint8)
    feat=[]
    for c in range(3):
        v=a[:,:,c]; h,_=np.histogram(v,bins=16,range=(0,256));feat.extend((h/h.sum()).tolist())
        feat.extend([float(v.mean()/255),float(v.std()/255)])
    m=metrics(file); feat.extend([m[k] for k in ['green_fraction','yellow_fraction','brown_fraction','sharpness']])
    # coarse non-spatial descriptor; intentionally documented as baseline
    lum=a.mean(axis=2).astype('float32')
    for s in np.array_split(lum,4,axis=0):
        feat.append(float(s.mean()/255))
    return np.array(feat,dtype=float)

def status():
    if VMETA.exists() and VMODEL.exists():return json.loads(VMETA.read_text(encoding='utf-8'))
    return None

def train():
    images=[r for r in db.rows('SELECT p.*, x.species FROM photos p JOIN plants x ON x.id=p.plant_id WHERE TRIM(p.label) != ""') if (PHOTO_DIR/r['filename']).exists()]
    groups_by_label={}
    for im in images:groups_by_label.setdefault(im['label'],set()).add(im['plant_id'])
    if len(groups_by_label)<2 or min(map(len,groups_by_label.values()))<3:
        raise ValueError('Se requieren al menos 2 etiquetas y 3 plantas distintas por etiqueta, con fotos etiquetadas, para una evaluación básica sin mezclar plantas.')
    X=np.vstack([feature_vector(PHOTO_DIR/im['filename']) for im in images]);y=np.array([im['label'] for im in images]);groups=np.array([im['plant_id'] for im in images])
    split=None
    for tr,te in GroupShuffleSplit(n_splits=150,test_size=.30,random_state=42).split(X,y,groups):
        if set(y[tr])==set(y) and set(y[te])==set(y):split=tr,te;break
    if split is None:raise ValueError('No hay suficiente variedad por planta para evaluar todas las clases sin fuga de datos.')
    tr,te=split
    choices={'Extra Trees':ExtraTreesClassifier(n_estimators=180,random_state=42,class_weight='balanced',min_samples_leaf=2,n_jobs=-1),
             'Random Forest':RandomForestClassifier(n_estimators=180,random_state=42,class_weight='balanced',min_samples_leaf=2,n_jobs=-1)}
    scores={}
    for name,alg in choices.items():
        alg.fit(X[tr],y[tr]);scores[name]=round(float(accuracy_score(y[te],alg.predict(X[te]))),4)
    best=max(scores,key=scores.get)
    model=choices[best];model.fit(X,y)
    joblib.dump(model,VMODEL)
    result={'model':best,'scores':scores,'test_accuracy_exploratory':scores[best], 'photos':len(images),
            'plants':len(set(groups)), 'labels':sorted(map(str,set(y))),
            'note':'Clasificador basal de color/textura, no análisis fitopatológico validado; confirmar con experto y conjunto independiente por planta/sitio.'}
    VMETA.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return result

def classify(file:Path):
    if not VMODEL.exists():return {'status':'sin_modelo','message':'Fotografía guardada. Aún no hay un modelo visual entrenado con ejemplos etiquetados.'}
    model=joblib.load(VMODEL)
    preds=sorted([{'label':str(label),'score':round(float(p),4)} for label,p in zip(model.classes_,model.predict_proba([feature_vector(file)])[0])], key=lambda x:-x['score'])
    if preds[0]['score']<.65:
        return {'status':'requiere_revision','top':preds[:3], 'message':'Confianza baja del modelo visual exploratorio; requiere revisión humana.'}
    return {'status':'clasificacion_exploratoria','top':preds[:3], 'message':'Clasificación exploratoria, NO diagnóstico confirmado. Requiere valoración agronómica.'}
