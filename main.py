from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from innertube import InnerTube
import os
import urllib.parse
import time  # ← AGREGAR esta línea
import httpx
import test_innertube

# 🍪 Cookies de sesión real para bypasear detección de bot
YOUTUBE_COOKIES = {
    'VISITOR_INFO1_LIVE': 'Q5iMtBhldt0',
    'PREF': 'f4=4000000&f6=40000000&tz=America.Lima&f7=100',
}

VISITOR_DATA = "CgtMSkFjYjIwcnd6QSju7ePIBjIKCgJQRRIEGgAgOzoKILjv1fvit63iaFi9_qu88sfksHM%3D"

app = FastAPI()


music_client = InnerTube(
    client_name="WEB_REMIX",
   client_version="1.20231219.01.00"
) 


# 📂 Crear carpeta "media" si no existe
MEDIA_DIR = "media"
os.makedirs(MEDIA_DIR, exist_ok=True)

# 🚀 Servir archivos locales (videos descargados para offline)
app.mount("/media", StaticFiles(directory=MEDIA_DIR), name="media")

# 🎯 Cliente InnerTube (mismo que usa MuseUp)
client = InnerTube(
    client_name="ANDROID",
    client_version="19.09.37",
)

# 🏓 Endpoint para keep-alive (mantener el servidor despierto)
@app.get("/ping")
async def ping():
    return {"status": "alive", "timestamp": time.time()}

@app.get("/video-info")
async def video_info(url: str = Query(...)):
    try:
        # Extraer video ID
        if "watch?v=" in url:
            video_id = url.split("watch?v=")[1].split("&")[0]
        elif "youtu.be/" in url:
            video_id = url.split("youtu.be/")[1].split("?")[0]
        else:
            return JSONResponse({"error": "URL inválida"}, status_code=400)

        print(f"🎵 Video: {video_id}")

        # Inyectar visitorData al contexto del cliente
        if hasattr(client, 'context'):
            if 'client' not in client.context:
                client.context['client'] = {}
            client.context['client']['visitorData'] = VISITOR_DATA

        # Hacer petición
        data = client.player(video_id=video_id)

        # Verificar streamingData
        if 'streamingData' not in data or not data.get('streamingData'):
            return JSONResponse({
                "error": "No disponible",
                "video_id": video_id
            }, status_code=404)

        streaming_data = data['streamingData']
        
        # Obtener URL del primer formato disponible
        stream_url = None
        
        # Intentar formatos combinados primero
        if 'formats' in streaming_data and len(streaming_data['formats']) > 0:
            stream_url = streaming_data['formats'][0].get('url')
        
        # Si no, intentar formatos adaptativos
        if not stream_url and 'adaptiveFormats' in streaming_data:
            for fmt in streaming_data['adaptiveFormats']:
                if fmt.get('url'):
                    stream_url = fmt['url']
                    break

        if not stream_url:
            return JSONResponse({"error": "No stream URL"}, status_code=404)

        # Metadata
        video_details = data.get('videoDetails', {})

        return {
            "title": video_details.get("title", ""),
            "duration": int(video_details.get("lengthSeconds", 0)),
            "thumbnail": video_details.get("thumbnail", {}).get("thumbnails", [{}])[-1].get("url", ""),
            "stream_url": stream_url,
            "video_id": video_id,
        }

    except Exception as e:
        print(f"❌ Error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)
    
@app.get("/search")
async def search_videos(query: str):
    try:
        videos = []
        search_variants = [query, f"{query} official music", f"{query} lyrics", f"{query} audio"]

        for variant in search_variants:
            response = client.search(variant)

            for section in response.get("contents", {}).get("twoColumnSearchResultsRenderer", {}).get("primaryContents", {}).get("sectionListRenderer", {}).get("contents", []):
                items = section.get("itemSectionRenderer", {}).get("contents", [])
                for item in items:
                    video = item.get("videoRenderer")
                    if video:
                        videos.append({
                            "videoId": video.get("videoId"),
                            "title": video.get("title", {}).get("runs", [{}])[0].get("text", ""),
                            "channel": video.get("ownerText", {}).get("runs", [{}])[0].get("text", ""),
                            "thumbnail": video.get("thumbnail", {}).get("thumbnails", [{}])[-1].get("url", ""),
                            "duration": video.get("lengthText", {}).get("simpleText", "")
                        })

            # Si ya hay 50, cortamos para no abusar
            if len(videos) >= 30:
                break

        # Eliminar duplicados por videoId
        unique_videos = {v["videoId"]: v for v in videos}.values()

        return {"results": list(unique_videos)[:30]}

    except Exception as e:
        return {"error": str(e)}

# 🔹 Variables de caché
cached_trending = None
cached_time = 0
CACHE_DURATION = 24 * 60 * 60  # 24 horas en segundos

@app.get("/browse")
async def browse_trending():
    global cached_trending, cached_time

    # ✅ Si el caché sigue vigente, devolver al instante
    if cached_trending and (time.time() - cached_time < CACHE_DURATION):
        return {"results": cached_trending}

    try:
        # 🔹 Buscar tendencias musicales recientes
        response = client.search("latest trending songs 2025")
        import json
        if isinstance(response, str):
            response = json.loads(response)

        videos = []

        # Extraemos solo los "videoRenderer" (no playlists ni mixes)
        for section in response.get("contents", {}).get("twoColumnSearchResultsRenderer", {}).get("primaryContents", {}).get("sectionListRenderer", {}).get("contents", []):
            items = section.get("itemSectionRenderer", {}).get("contents", [])
            for item in items:
                video = item.get("videoRenderer")
                if video:
                    title = video.get("title", {}).get("runs", [{}])[0].get("text", "").lower()

                    # ⚡️Filtro más equilibrado: evita tops, mixes, playlists, compilaciones
                    if any(word in title for word in ["songs", "playlist", "mix", "top", "best of", "full album", "hits"]):
                        continue

                    videos.append({
                        "videoId": video.get("videoId"),
                        "title": video.get("title", {}).get("runs", [{}])[0].get("text", ""),
                        "channel": video.get("ownerText", {}).get("runs", [{}])[0].get("text", ""),
                        "thumbnail": video.get("thumbnail", {}).get("thumbnails", [{}])[-1].get("url", ""),
                        "duration": video.get("lengthText", {}).get("simpleText", "")
                    })

        # 🔸 Si aún hay pocos resultados, usar una búsqueda de respaldo
        if len(videos) < 15:
            backup = client.search("new songs 2025 official music video")
            if isinstance(backup, str):
                backup = json.loads(backup)

            for section in backup.get("contents", {}).get("twoColumnSearchResultsRenderer", {}).get("primaryContents", {}).get("sectionListRenderer", {}).get("contents", []):
                items = section.get("itemSectionRenderer", {}).get("contents", [])
                for item in items:
                    video = item.get("videoRenderer")
                    if video:
                        title = video.get("title", {}).get("runs", [{}])[0].get("text", "").lower()
                        if any(word in title for word in ["playlist", "mix", "top", "best of", "full album", "hits"]):
                            continue
                        videos.append({
                            "videoId": video.get("videoId"),
                            "title": video.get("title", {}).get("runs", [{}])[0].get("text", ""),
                            "channel": video.get("ownerText", {}).get("runs", [{}])[0].get("text", ""),
                            "thumbnail": video.get("thumbnail", {}).get("thumbnails", [{}])[-1].get("url", ""),
                            "duration": video.get("lengthText", {}).get("simpleText", "")
                        })

        # 🔹 Priorizar videos oficiales
        videos.sort(
            key=lambda v: (
                "(official video)" not in v["title"].lower() and
                "(video oficial)" not in v["title"].lower()
            )
        )

        # 🔸 Limitar a 30 resultados
        videos = videos[:30]

        # ✅ Guardar en caché
        cached_trending = videos
        cached_time = time.time()

        return {"results": videos}

    except Exception as e:
        return {"error": str(e)}
    
@app.get("/test-innertube")
def test_innertube_route():
    import io
    import sys

    buffer = io.StringIO()
    sys.stdout = buffer

    try:
        exec(open("test_innertube.py").read())
        output = buffer.getvalue()
    except Exception as e:
        output = f"Error ejecutando test: {e}"

    sys.stdout = sys.__stdout__
    return {"result": output}
    
    # ==========================
# 🎵 NUEVOS ENDPOINTS POR CATEGORÍA
# ==========================

@app.get("/category/songs")
async def category_songs(category: str):
    """
    Devuelve canciones principales (videos musicales) de una categoría.
    Ejemplo: /category/songs?category=rock
    """
    try:
        query = f"{category} music"
        response = client.search(query)

        import json
        if isinstance(response, str):
            response = json.loads(response)

        videos = []

        for section in response.get("contents", {}).get("twoColumnSearchResultsRenderer", {}).get(
            "primaryContents", {}
        ).get("sectionListRenderer", {}).get("contents", []):
            items = section.get("itemSectionRenderer", {}).get("contents", [])
            for item in items:
                video = item.get("videoRenderer")
                if video:
                    title = video.get("title", {}).get("runs", [{}])[0].get("text", "").lower()

                    # 🔹 Evitar playlists, mixes, tops, compilaciones
                    if any(word in title for word in ["playlist", "mix", "top", "best of", "full album", "hits"]):
                        continue

                    videos.append({
                        "video_id": video.get("videoId"),
                        "title": video.get("title", {}).get("runs", [{}])[0].get("text", ""),
                        "author": video.get("ownerText", {}).get("runs", [{}])[0].get("text", ""),
                        "thumbnail": video.get("thumbnail", {}).get("thumbnails", [{}])[-1].get("url", ""),
                        "stream_url": None  # Se obtiene luego al reproducir
                    })

        # 🔸 Priorizar videos oficiales
        videos.sort(
            key=lambda v: (
                "(official video)" not in v["title"].lower() and
                "(video oficial)" not in v["title"].lower()
            )
        )

        return {"results": videos[:25]}

    except Exception as e:
        return {"error": str(e)}


@app.get("/category/playlists")
def get_category_playlists(category: str = Query(..., description="Nombre de la categoría (ej. 'rock', 'pop', 'rap')")):
    try:
        # ✅ Búsqueda general y filtrar por tipo "playlist"
        response = music_client.search(query=category)
        
        playlists = []
        
        # Navegar por la estructura de respuesta
        contents = response.get("contents", {})
        tabs = contents.get("tabbedSearchResultsRenderer", {}).get("tabs", [])
        
        if not tabs:
            return {"results": []}
        
        sections = tabs[0].get("tabRenderer", {}).get("content", {}).get("sectionListRenderer", {}).get("contents", [])
        
        for section in sections:
            shelf = section.get("musicShelfRenderer", {})
            items = shelf.get("contents", [])
            
            for item in items:
                data = item.get("musicResponsiveListItemRenderer", {})
                
                # ✅ Verificar que sea una playlist
                nav_endpoint = data.get("navigationEndpoint", {})
                browse_id = nav_endpoint.get("browseEndpoint", {}).get("browseId", "")
                
                # Las playlists tienen browseId que empieza con "VL" o "RDAMPL"
                if not (browse_id.startswith("VL") or browse_id.startswith("RDAMPL")):
                    continue
                
                # Extraer información
                flex_columns = data.get("flexColumns", [])
                if len(flex_columns) < 1:
                    continue
                
                title_data = flex_columns[0].get("musicResponsiveListItemFlexColumnRenderer", {}).get("text", {}).get("runs", [])
                title = title_data[0].get("text", "") if title_data else ""
                
                author = ""
                if len(flex_columns) > 1:
                    author_data = flex_columns[1].get("musicResponsiveListItemFlexColumnRenderer", {}).get("text", {}).get("runs", [])
                    author = author_data[0].get("text", "") if author_data else ""
                
                thumbnail_data = data.get("thumbnail", {}).get("musicThumbnailRenderer", {}).get("thumbnail", {}).get("thumbnails", [])
                thumbnail = thumbnail_data[-1].get("url", "") if thumbnail_data else ""
                
                playlist = {
                    "video_id": browse_id,
                    "title": title,
                    "author": author,
                    "thumbnail": thumbnail,
                    "description": "",
                }
                
                playlists.append(playlist)
        
        return {"results": playlists[:20]}
    
    except Exception as e:
        print(f"Error en playlists: {e}")
        return {"error": str(e), "results": []}


@app.get("/category/albums")
def get_category_albums(category: str = Query(..., description="Nombre de la categoría (ej. 'rock', 'pop', 'rap')")):
    try:
        response = music_client.search(query=category, params="EgWKAQIYAWoKEAMQBBAJEAo%3D")
        sections = response.get("contents", {}).get("tabbedSearchResultsRenderer", {}).get("tabs", [])[0] \
            .get("tabRenderer", {}).get("content", {}).get("sectionListRenderer", {}).get("contents", [])

        albums = []
        for section in sections:
            items = section.get("musicShelfRenderer", {}).get("contents", [])
            for item in items:
                data = item.get("musicResponsiveListItemRenderer", {})
                album = {
                    "video_id": data.get("navigationEndpoint", {}).get("browseEndpoint", {}).get("browseId"),
                    "title": data.get("flexColumns", [])[0]["musicResponsiveListItemFlexColumnRenderer"]["text"]["runs"][0]["text"],
                    "author": data.get("flexColumns", [])[1]["musicResponsiveListItemFlexColumnRenderer"]["text"]["runs"][0]["text"] if len(data.get("flexColumns", [])) > 1 else None,
                    "thumbnail": data.get("thumbnail", {}).get("musicThumbnailRenderer", {}).get("thumbnail", {}).get("thumbnails", [{}])[-1].get("url"),
                }
                albums.append(album)
        
        # ✅ Devolver con "results" en lugar de "albums"
        return {"results": albums[:20]}
    except Exception as e:
        return {"error": str(e), "results": []}
    