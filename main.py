from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from innertube import InnerTube
import os
import urllib.parse
import time  # ← AGREGAR esta línea

app = FastAPI()

# 📂 Crear carpeta "media" si no existe
MEDIA_DIR = "media"
os.makedirs(MEDIA_DIR, exist_ok=True)

# 🚀 Servir archivos locales (videos descargados para offline)
app.mount("/media", StaticFiles(directory=MEDIA_DIR), name="media")

# 🎯 Cliente InnerTube (mismo que usa MuseUp)
client = InnerTube("ANDROID")


@app.get("/video-info")
async def video_info(url: str = Query(...)):
    try:
        start_time = time.time()  # ← AGREGAR esta línea
        # Extraer video ID de la URL
        if "watch?v=" in url:
            video_id = url.split("watch?v=")[1].split("&")[0]
        elif "youtu.be/" in url:
            video_id = url.split("youtu.be/")[1].split("?")[0]
        else:
            return JSONResponse({"error": "URL de YouTube inválida"}, status_code=400)

        print(f"🎵 Obteniendo info para video: {video_id}")

        # ⚡ Obtener datos del video con InnerTube
        before_innertube = time.time()  # ← AGREGAR
        data = client.player(video_id=video_id)
        after_innertube = time.time()  # ← AGREGAR
        print(f"⏱️ InnerTube tardó: {after_innertube - before_innertube:.2f}s")  # ← AGREGAR

        # 🔍 Extraer streamingData
        if 'streamingData' not in data:
            return JSONResponse({"error": "No se pudo obtener streamingData"}, status_code=404)

        streaming_data = data['streamingData']
        
        # 🎬 Obtener el mejor formato (con audio y video)
        if 'formats' in streaming_data and len(streaming_data['formats']) > 0:
            # Formatos combinados (audio + video)
            best_format = streaming_data['formats'][0]
            stream_url = best_format.get('url')
        elif 'adaptiveFormats' in streaming_data:
            # Formatos adaptativos (separados)
            # Buscar el mejor video
            video_formats = [f for f in streaming_data['adaptiveFormats'] 
                           if f.get('mimeType', '').startswith('video')]
            if video_formats:
                best_format = max(video_formats, key=lambda x: x.get('height', 0))
                stream_url = best_format.get('url')
            else:
                return JSONResponse({"error": "No se encontraron formatos de video"}, status_code=404)
        else:
            return JSONResponse({"error": "No se encontraron formatos disponibles"}, status_code=404)

        if not stream_url:
            return JSONResponse({"error": "No se pudo obtener URL del stream"}, status_code=404)

        # 📊 Metadata
        video_details = data.get('videoDetails', {})

        total_time = time.time() - start_time  # ← AGREGAR
        print(f"⏱️ Tiempo total backend: {total_time:.2f}s")  # ← AGREGAR
        
        return {
            "title": video_details.get("title", "Sin título"),
            "duration": int(video_details.get("lengthSeconds", 0)),
            "thumbnail": video_details.get("thumbnail", {}).get("thumbnails", [{}])[-1].get("url", ""),
            "stream_url": stream_url,
            "video_id": video_id,
        }

    except Exception as e:
        print(f"❌ Error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)