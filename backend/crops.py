"""Crop recommendation (tabular) is NOT a plant disease detector."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd
import joblib
from sklearn.ensemble import RandomForestClassifier, ExtraTreesClassifier, HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.model_selection import GroupShuffleSplit
from sklearn.metrics import accuracy_score, classification_report

ROOT=Path(__file__).resolve().parents[1]
MODEL=ROOT/'storage/models/crops.joblib'
META=ROOT/'storage/models/crops_meta.json'
FEATURES=['N','P','K','temperature','humidity','ph','rainfall']

class DataError(ValueError): pass

def data_profile(path:Path):
    df=pd.read_csv(path,encoding='utf-8-sig')
    missing=[x for x in FEATURES+['label'] if x not in df.columns]
    if missing: raise DataError('Faltan columnas: '+', '.join(missing))
    df=df.dropna(subset=['label']).copy()
    for f in FEATURES: df[f]=pd.to_numeric(df[f],errors='coerce')
    df['label']=df.label.astype(str).str.strip()
    df=df[df.label.ne('') & df[FEATURES].notna().all(axis=1)].copy()
    if len(df)<30 or df.label.nunique()<2:raise DataError('Se necesitan al menos 30 registros completos de 2 clases.')
    groups=pd.util.hash_pandas_object(df[FEATURES+['label']],index=False).values
    return df,groups

def train(path:Path):
    df,groups=data_profile(path)
    X,y=df[FEATURES],df['label']
    duplicates=int(len(df)-pd.Series(groups).nunique())
    # Find a split with all classes represented in both partitions if possible.
    split=None
    for tr,te in GroupShuffleSplit(n_splits=70,test_size=.22,random_state=42).split(X,y,groups):
        if len(set(y.iloc[tr]))==y.nunique() and len(set(y.iloc[te]))==y.nunique():
            split=tr,te; break
    if split is None:
        raise DataError('No es posible evaluar todas las clases sin mezclar duplicados. Agrega más registros originales independientes de cada clase.')
    tr,te=split
    makers={
        'Random Forest':RandomForestClassifier(n_estimators=180,min_samples_leaf=2,random_state=42,n_jobs=-1,class_weight='balanced_subsample'),
        'Extra Trees':ExtraTreesClassifier(n_estimators=180,min_samples_leaf=2,random_state=42,n_jobs=-1,class_weight='balanced'),
        'HistGradientBoosting':HistGradientBoostingClassifier(max_iter=130,l2_regularization=1.0,random_state=42)
    }
    scores={}; bestname=''; bestscore=-1; chosen=None
    for name,alg in makers.items():
        pipeline=Pipeline([('imputer',SimpleImputer(strategy='median')),('classifier',alg)])
        pipeline.fit(X.iloc[tr],y.iloc[tr]); score=float(accuracy_score(y.iloc[te],pipeline.predict(X.iloc[te])))
        scores[name]=round(score,4)
        if score>bestscore:bestname=name;bestscore=score;chosen=pipeline
    # Final model refit on all training data. Test score refers to prior held-out split only.
    final=Pipeline([('imputer',SimpleImputer(strategy='median')),('classifier',makers[bestname])])
    final.fit(X,y)
    MODEL.parent.mkdir(parents=True,exist_ok=True)
    joblib.dump({'model':final,'features':FEATURES},MODEL)
    meta={'model':bestname,'accuracy_holdout':round(bestscore,4), 'scores':scores,
          'rows':len(df),'duplicates_removed_from_split':duplicates,
          'distinct_crops':int(y.nunique()),'source':path.name,
          'test_rows':int(len(te)),'train_rows':int(len(tr)),
          'evaluation':'Separación por grupos de filas idénticas; NO prueba validez para Sinaloa, invernadero o cultivos reales.'}
    META.write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
    return meta

def model_status():
    if META.exists() and MODEL.exists():
        return json.loads(META.read_text(encoding='utf-8'))
    return None

def predict(d):
    if not MODEL.exists():raise DataError('Primero entrena el clasificador de cultivos.')
    row={}
    for k in FEATURES:
        try:row[k]=float(d[k])
        except (KeyError,TypeError,ValueError):raise DataError('Introduce un valor numérico para '+k)
        if not np.isfinite(row[k]):raise DataError('Hay valores no finitos.')
    if not 0<=row['humidity']<=100 or not 0<=row['ph']<=14 or not all(row[k]>=0 for k in ['N','P','K','rainfall']):
        raise DataError('Revisa los rangos: humedad 0–100, pH 0–14, NPK/precipitación no negativos.')
    model=joblib.load(MODEL)['model']
    probs=model.predict_proba(pd.DataFrame([row]))[0]
    cls=model.classes_
    return {'predictions': sorted([{'label':str(a),'probability':round(float(b),4)} for a,b in zip(cls,probs)],key=lambda x:-x['probability'])[:5],
            'disclaimer':'Probabilidades del modelo, no probabilidades calibradas de éxito. Datos ajenos a este invernadero; validar su procedencia y unidades.'}
