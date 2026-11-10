"""Heuristic rotation planner retained from AgroIA. Educational; NOT a crop plan validated for a site."""
from __future__ import annotations
import math
import random

FAMILIES={
 'arroz':'poaceae','maiz':'poaceae','trigo':'poaceae','sorgo':'poaceae',
 'frijol':'fabaceae','garbanzo':'fabaceae','soya':'fabaceae',
 'algodon':'malvaceae','tomate':'solanaceae','papa':'solanaceae','chile':'solanaceae',
 'yuca':'euphorbiaceae','naranja':'rutaceae','ñame':'dioscoreaceae'
}

def plan(probabilities,previous='',seasons=4,algorithm='recocido',seed=42):
    if algorithm not in ['recocido','tabu']:raise ValueError('Algoritmo no permitido')
    if not 2<=seasons<=8:raise ValueError('Ciclos: 2 a 8')
    candidates=[x['label'] for x in probabilities[:8]]
    weights={x['label']:float(x['probability']) for x in probabilities}
    if not candidates:raise ValueError('No hay recomendaciones para planificar')
    rng=random.Random(seed)
    def score(seq):
        total=sum(weights.get(c,0) for c in seq)
        chain=([previous] if previous else [])+list(seq)
        penalty=0; bonus=0
        for a,b in zip(chain,chain[1:]):
            fam_a=FAMILIES.get(a);fam_b=FAMILIES.get(b)
            if a==b:penalty+=0.8
            elif fam_a and fam_b and fam_a==fam_b:penalty+=0.35
            if fam_b=='fabaceae' and fam_a and fam_a!='fabaceae':bonus+=0.08
        return total-penalty+bonus
    current=[rng.choice(candidates) for _ in range(seasons)]
    best=current[:];best_score=score(best)
    tabu=[];iterations=1200
    for k in range(iterations):
        neighbor=current[:];j=rng.randrange(seasons);neighbor[j]=rng.choice(candidates)
        now_score=score(current);try_score=score(neighbor)
        if algorithm=='recocido':
            temperature=max(.008,1.35*(.995**k))
            if try_score>=now_score or rng.random()<math.exp(max(-700,(try_score-now_score)/temperature)):
                current=neighbor
        else:
            key=tuple(neighbor)
            if key not in tabu or try_score>best_score:
                if try_score>=now_score or rng.random()<.05:current=neighbor
                tabu.append(key);tabu=tabu[-80:]
        result=score(current)
        if result>best_score:best_score=result;best=current[:]
    return {'plan':[{'cycle':i+1,'crop':name,'family':FAMILIES.get(name,'no determinada')} for i,name in enumerate(best)],
            'score':round(best_score,4),'algorithm':algorithm,'iterations':iterations,
            'warning':'Puntuación heurística relativa; no está calibrada a rendimiento agrícola, clima, disponibilidad de agua, manejo sanitario ni calendario. Debe revisarse con un agrónomo.'}
