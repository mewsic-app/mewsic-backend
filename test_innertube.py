from innertube import InnerTube
import json
import time

video_id = "hTWKbfoikeg"  # Smells Like Teen Spirit

clients = [
    "ANDROID",
    "ANDROID_MUSIC",
    "WEB",
    "WEB_REMIX",
    "TVHTML5",
    "IOS"
]

print(f"\n🎬 Probando InnerTube con video ID: {video_id}\n")

for name in clients:
    print(f"🧩 Cliente: {name}")
    try:
        start = time.time()
        client = InnerTube(name)
        data = client.player(video_id)
        elapsed = time.time() - start

        title = data.get("videoDetails", {}).get("title", "❌ No title")
        streaming = "✅ streamingData OK" if "streamingData" in data else "❌ Sin streamingData"

        print(f"⏱️ Tiempo: {elapsed:.2f}s")
        print(f"🎵 Título: {title}")
        print(f"📡 Estado: {streaming}\n")

    except Exception as e:
        print(f"⚠️ Error con {name}: {e}\n")

print("\n✅ Prueba completada.\n")