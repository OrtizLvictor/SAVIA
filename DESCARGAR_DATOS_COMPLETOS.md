# Agregar 5 000 registros publicados por Zenodo

En una terminal dentro de la carpeta SAVIA:

```bash
python datasets/descargar_datasets_agroia.py
```

Busca el archivo `datasets/descargados/agroia_zenodo_5000_ES.csv`.

Desde **Centro de entrenamiento → Importar CSV**, selecciónalo y después pulsa **Entrenar**. El entrenamiento se realiza en tu máquina y la evaluación sigue siendo exploratoria. El script además intenta descargar datos SIAP y NASA como referencia, **no** para entrenar NPK de cultivos ni detectar enfermedades.

Si falla, abre el enlace oficial https://zenodo.org/records/19709807 y revisa tu conexión. No mezcles variantes sintéticas, archivos duplicados ni traducciones del mismo conjunto como si fueran observaciones independientes.
