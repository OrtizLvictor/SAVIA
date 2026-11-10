"""Run local SAVIA server and open the browser automatically."""
import os, socket, threading, time, webbrowser
import uvicorn

def open_browser():
    for _ in range(240):
        try:
            with socket.create_connection(('127.0.0.1',8765),timeout=0.4):
                webbrowser.open('http://127.0.0.1:8765')
                return
        except OSError:
            time.sleep(.5)

if __name__=='__main__':
    print('SAVIA Studio • http://127.0.0.1:8765')
    print('Cierra con Ctrl+C. Datos privados almacenados localmente en storage/.')
    if os.environ.get('SAVIA_NO_BROWSER')!='1':
        threading.Thread(target=open_browser,daemon=True).start()
    uvicorn.run('backend.app:app',host='127.0.0.1',port=8765,log_level='warning')


#EJECUTA EN TU CONSOLA bash ARRANCAR_UBUNUTU.sh