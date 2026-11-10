#!/usr/bin/env python3
"""Descarga datos publicados y prepara CSVs para AgroIA Pro.
Uso: python3 descargar_datasets_agroia.py
Internet necesario. Solo biblioteca estándar de Python; Windows/Linux.
"""
import csv
import hashlib
import io
import json
import ssl
import sys
from collections import Counter
from pathlib import Path
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parent
OUT = HERE / 'descargados'
OUT.mkdir(parents=True, exist_ok=True)
ZENODO = 'https://zenodo.org/records/19709807/files/original_dataset.csv?download=1'
ZENODO_MD5 = '80822638d28b12deaf4f68ae1dfef3ce'
SIAP = 'https://nube.agricultura.gob.mx/index.php?ANIO=2025&view=10AE434F-A2158368-A120BC5A-EDF4AFAA'
NASA = ('https://power.larc.nasa.gov/api/temporal/daily/point'
        '?parameters=T2M,RH2M,PRECTOTCORR&community=AG'
        '&longitude=-107.39&latitude=24.81&start=20250101&end=20251231&format=JSON')
TRANSLATE = {
    'maize':'maiz', 'rice':'arroz', 'soybean':'soya', 'beans':'frijol',
    'guinea_corn':'sorgo', 'pepper':'chile', 'tomatoes':'tomate',
    'cassava':'yuca', 'orange':'naranja', 'yam':'ñame'
}
FEATURES = ['N', 'P', 'K', 'temperature', 'humidity', 'ph', 'rainfall']

def get(url, timeout=70):
    req=Request(url, headers={'User-Agent':'Mozilla/5.0 AgroIA-Pro-dataset-loader/1.0','Accept':'*/*'})
    with urlopen(req,timeout=timeout,context=ssl.create_default_context()) as r:
        raw=r.read()
    if raw.lstrip().lower().startswith((b'<!doctype html', b'<html')):
        raise RuntimeError('El servidor devolvio HTML, no el archivo de datos esperado.')
    return raw

def get_zenodo():
    b=get(ZENODO)
    digest=hashlib.md5(b).hexdigest()
    if digest != ZENODO_MD5:
        raise ValueError(f'El archivo Zenodo no coincide con el MD5 publicado: {digest}')
    (OUT/'zenodo_original_5000.csv').write_bytes(b)
    rows=list(csv.DictReader(io.StringIO(b.decode('utf-8-sig'))))
    must=FEATURES+['crop_label']; missing=[x for x in must if x not in rows[0]]
    if missing:raise ValueError('Faltan columnas del dataset: '+repr(missing))
    print('Zenodo:',len(rows),'registros, cultivos',dict(Counter(x['crop_label'] for x in rows)))
    for translate in (False,True):
        name = 'agroia_zenodo_5000_ES.csv' if translate else 'agroia_zenodo_5000_original_labels.csv'
        with (OUT/name).open('w',newline='',encoding='utf-8-sig') as f:
            fieldnames = FEATURES+['label','soil']
            w=csv.DictWriter(f,fieldnames=fieldnames)
            w.writeheader()
            for r in rows:
                label=r['crop_label'].strip()
                if translate:label=TRANSLATE.get(label,label)
                item={k:r[k] for k in FEATURES}
                item.update({'label':label,'soil':r.get('soil','').strip()})
                w.writerow(item)
        print('Archivo de entrenamiento listo:',OUT/name)
    print('Advertencia: no mezcles los dos archivos; son los mismos registros con etiquetas traducidas.')

def get_siap():
    b=get(SIAP)
    if len(b)<15000:raise ValueError('Descarga SIAP demasiado pequena para el archivo anual esperado.')
    outfile=OUT/'SIAP_Mexico_produccion_2025_original.csv'
    outfile.write_bytes(b)
    print('Archivo oficial complementario:',outfile,'('+str(len(b))+' bytes)')

def get_nasa():
    b=get(NASA)
    d=json.loads(b)
    meta=d.get('properties',{}).get('parameter',{})
    if not all(k in meta for k in ['T2M','RH2M','PRECTOTCORR']):
        raise ValueError('NASA devolvio parametros inesperados: '+str(list(meta)))
    days=sorted(meta['T2M'])
    outfile=OUT/'NASA_POWER_Culiacan_clima_2025.csv'
    with outfile.open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.writer(f); w.writerow(['date','temperature_c','humidity_pct','rainfall_mm','source'])
        for day in days:
            vals=[meta[k].get(day) for k in ['T2M','RH2M','PRECTOTCORR']]
            vals=['' if v in (-999,-999.0,None) else v for v in vals]
            w.writerow([day[:4]+'-'+day[4:6]+'-'+day[6:],*vals,'NASA POWER'])
    print('Archivo oficial complementario:',outfile, 'dias:',len(days))

def main():
    failures=0
    for title,func in [('ZENODO / ENTRENAMIENTO',get_zenodo),('DGSIAP / PRODUCCION 2025',get_siap),('NASA / CLIMA CULIACAN',get_nasa)]:
        print('\nDescargando:',title)
        try:func()
        except Exception as e:
            failures+=1
            print('No se pudo descargar:',type(e).__name__,str(e))
    print('\nRuta:',OUT)
    print('Solo los CSV de Zenodo llamados agroia_zenodo_... son para el boton Entrenar de AgroIA Pro.')
    if failures:
        print('Fallaron',failures,'fuentes. Revisa conexion y prueba los enlaces originales del README.')
    return 0 if failures==0 else 1

if __name__=='__main__':sys.exit(main())
