# SAVIA Studio v1.0 · Invernadero Científico

**Sistema de Análisis Visual e Inteligencia Agrícolac**

Aplicación con interfaz web local, barra lateral plegable, tema oscuro/claro, plantas identificadas, fotografías, registros de sensores, entrenamientos tabulares y visuales separados, recomendación exploratoria de cultivos, planificador de rotación con recocido simulado y búsqueda tabú, pronóstico Open-Meteo y asistente local con integración Ollama opcional.

## Inicio rápido

### En Ubuntu o Linux

1. Extrae **toda** la carpeta `SAVIA_Studio_v1` del ZIP en tu equipo.
2. Abre una terminal en esa carpeta.
3. Ejecuta:

```bash
bash ARRANCAR_UBUNTU.sh
```

El script prepara un entorno virtual de Python e instala dependencias **sin modificar tus repositorios APT**. Necesitas Python 3.11 o superior, `python3-venv` y acceso a PyPI la primera vez. No uses `sudo` para iniciar SAVIA.

### En Windows 10/11

Instala Python 3.11–3.13 desde python.org (habilita Python en PATH). Extrae el ZIP y abre `ARRANCAR_WINDOWS.bat`.

En ambos sistemas se abre automáticamente **http://127.0.0.1:8765**; si no se abre, escribe esa dirección en el navegador. Mantén abierta la ventana de la terminal. Detén el programa con **Ctrl+C**.

### Arranque manual

```bash
python -m venv .venv
# Ubuntu: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python iniciar.py
```

No hay nube ni cuentas obligatorias. Servicio vinculado solo a `127.0.0.1`, no abierto a internet o a la red local.

## Arquitectura

```text
Navegador (HTML/CSS/JS + captura de cámara con permiso)
       │ solicitudes HTTP locales
       ▼
FastAPI (backend/app.py)
       ├── SQLite (storage/savia.sqlite3)
       ├── imágenes JPG locales (storage/photos/)
       ├── motor tabular (backend/crops.py) + joblib
       ├── modelo visual experimental (backend/vision.py) + joblib
       ├── planificador (backend/planning.py)
       ├── Open-Meteo (pronóstico público, bajo demanda)
       └── Ollama opcional (respuestas generativas locales)
```

## Dataset incluido y su procedencia

- `datasets/AgroIA_Zenodo_muestra_100_ES.csv`: **100 filas recuperadas** del paquete de AgroIA previo. N, P, K, temperatura, humedad, pH, precipitación y `label` (cultivo), con etiquetas al español. **Se entrena automáticamente al primer inicio** si el entorno tiene las librerías necesarias.
- `datasets/AgroIA_Zenodo_muestra_100_original.csv`: **las mismas 100 observaciones** con etiquetas de cultivos originales en inglés. No las unas ni dupliques dentro de un entrenamiento.
- `datasets/LEEME_ORIGEN_DE_DATOS.txt`: nota conservada de tu paquete anterior con fuentes y limitaciones.
- `datasets/descargar_datasets_agroia.py`: descarga bajo demanda la fuente completa de Zenodo, y archivos complementarios de SIAP y NASA POWER **con internet en tu equipo**. Para obtener el CSV completo usa:

```bash
python datasets/descargar_datasets_agroia.py
```

Se guarda en `datasets/descargados/agroia_zenodo_5000_ES.csv`; luego impórtalo desde **Centro de entrenamiento → Importar CSV**. Si una fuente externa falla, el script lo dirá: no creará datos de reemplazo.

La referencia original comprobada es: Kwaghtyo, K. D., Eke, C. I., & Ajon, A. T. (2026). *Crop Recommendation Dataset with SMOTE, VAE and CropGAN Synthetic Generated Dataset Variants* [Dataset]. Zenodo. https://doi.org/10.5281/zenodo.19709807. Se recolectó en Nigeria, NO en Sinaloa. No se valida para este invernadero ni se conocen automáticamente las unidades locales de NPK.

**No entrenes detección de enfermedades con ese CSV.** No contiene etiquetas visuales ni imágenes de enfermedades.

## ¿Qué hace cada módulo?

1. **Vista general:** total real de plantas, fotos, lecturas, estado de modelos y eventos.
2. **Mis plantas:** registrar y eliminar plantas con identificador, especie, zona y fecha de siembra.
3. **Análisis visual:** cargar fotografía JPG/PNG/WEBP (máximo 9 MB), usar cámara del navegador si existe, asociarla a una planta, añadir etiqueta cuando haya verificación humana. Calcula porcentajes de colores y nitidez, no diagnósticos. Historial consultable por planta.
4. **Monitoreo y sensores:** capturar lecturas manuales con fecha y opcionalmente planta; gráficas de temperatura y humedad basadas **solo en datos almacenados**. Aún no se incluye controlador de hardware, protocolo de cámaras especializadas ni automatización real de bombas/ventiladores.
5. **Centro de entrenamiento:** comparar Random Forest, Extra Trees y HistGradientBoosting para recomendación de cultivos; subir otros CSV con el esquema `N,P,K,temperature,humidity,ph,rainfall,label`; clasificación visual experimental basada en histogramas de color, textura simple y modelos de árboles.
6. **Planificador de rotación:** dos metaheurísticas que maximizan una función heurística de puntuación relativa, penalización por repetición de cultivos/familia y ligera bonificación de leguminosas. No prueba beneficios agronómicos ni genera un calendario validado.
7. **Clima regional:** consultar el pronóstico Open-Meteo por latitud/longitud. Fuente exterior, no temperatura del prototipo.
8. **Hablar con SAVIA:** sin Ollama, respuestas locales basadas en reglas y registros, no lenguaje generativo. Opcionalmente usa **Ollama local** con un modelo instalado y accesible en `127.0.0.1:11434`. Si no hay servicio, queda funcional el modo local.

## Validación científica y seguridad

- El CSV inicial de solo 100 filas sirve para **pruebas de funcionamiento**, no para medir generalización ni tomar decisiones reales. La evaluación interna separa filas duplicadas exactas en el train/test, pero no garantiza separar parcelas, campañas, ubicaciones, datos relacionados o imágenes correlacionadas. **Una exactitud muy elevada en la muestra no valida resultados de campo.**
- Entrenamiento visual: exige al menos dos etiquetas distintas y **tres plantas distintas por clase**, separa plantas entre entrenamiento/prueba cuando es posible, pero sigue siendo un clasificador exploratorio de bajo nivel, no una red neuronal de diagnóstico fitopatológico ni una inspección multispectral.
- Si una foto no ha sido evaluada por especialista, deja la etiqueta en blanco. Para detectar enfermedades con rigor se requiere adquirir fotografías propias, etiquetas confirmadas, separar conjuntos por planta y lote, un conjunto de prueba externo y revisión de falsos positivos/negativos.
- Por defecto no hay datos de sensores ni fotografías prefabricados, y no se presenta el pronóstico como dato interno.
- La configuración es local de laboratorio: no la expongas a internet sin autenticación y protección adicionales.
- Los modelos guardados con joblib son archivos locales generados por tu propio entrenamiento; **no abras modelos joblib de terceros** por seguridad.

## Carpetas

```
SAVIA_Studio_v1/
├── iniciar.py                      # arranque y abre navegador
├── ARRANCAR_UBUNTU.sh              # un solo comando en Linux
├── ARRANCAR_WINDOWS.bat            # doble clic en Windows
├── requirements.txt
├── backend/                        # FastAPI y motores de IA
├── frontend/                       # interfaz moderna sin framework web
├── datasets/                       # CSV recuperados y descargador
├── storage/                        # SQLite, fotos y modelos (se crean al arrancar)
└── tests/test_savia.py             # pruebas sobre instalación descartable
```

## Mejoras pendientes para fase experimental

- Integración física de cámaras industriales, térmicas, multiespectrales o IP: definir fabricante, interfaz (RTSP/USB/SDK) y calibración. La aplicación usa actualmente cámara web estándar por permiso del navegador.
- Ingestión automatizada y verificada de sensores reales, con unidades, límites, identificación y sello horario.
- Modelo profundo (CNN) especializado en plantas del invernadero: entrenamiento con datos etiquetados, validación externa, curva de confusión, calibración de confianza y evaluación de enfermedades. **No se incluye un detector preentrenado de enfermedades sin evidencia.**
- Control seguro de bombas, ventilación e iluminación con mecanismos de seguridad independientes.

## Licencias y servicios externos

Aplicación experimental para uso académico. Bibliotecas FastAPI, scikit-learn, Pillow, pandas, requests y Uvicorn se instalan desde PyPI; comprueba sus condiciones de licencia. Open-Meteo tiene condiciones de uso propias. El dataset se cita por su DOI.
