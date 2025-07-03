import asyncio
import time
import json
import logging
from pathlib import Path
from typing import List, Optional
from aiohttp import web
from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaPlayer
import aiohttp_cors

logger = logging.getLogger("media.server")
logging.basicConfig(level=logging.INFO)

class MediaStreamingServer:
    def __init__(self, host='localhost', port=8765, media_dir='./media'):
        self.host = host
        self.port = port
        self.media_dir = Path(media_dir)
        self.media_dir.mkdir(exist_ok=True)
        self.latest_video_path: Optional[Path] = None
        self.webpcs: List[RTCPeerConnection] = []

    async def create_http_server(self):
        app = web.Application()
        app["server"] = self
        app.router.add_post('/enqueue-video', self.enqueue_video)
        app.router.add_post('/webrtc/offer', self.webrtc_offer)
        app.router.add_post('/webrtc/answer', self.webrtc_answer)

        cors = aiohttp_cors.setup(app, defaults={
            "*": aiohttp_cors.ResourceOptions(
                allow_headers='*',
                allow_credentials=True,
                expose_headers='*'
            )
        })
        for route in app.router.routes():
            cors.add(route)

        return app

    async def enqueue_video(self, request):
        data = await request.json()
        path = Path(data.get("path"))
        if path.exists() and path.suffix == ".mp4":
            self.latest_video_path = path
            logger.info(f"✅ Enqueued video chunk: {path.name}")
            return web.json_response({"status": "ok", "file": str(path)})
        else:
            logger.warning(f"❌ Failed to enqueue: {path}")
            return web.json_response({"error": "Invalid or missing video file"}, status=400)

    async def webrtc_offer(self, request):
        params = await request.json()
        offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])
        pc = RTCPeerConnection()
        self.webpcs.append(pc)

        if not self.latest_video_path or not self.latest_video_path.exists():
            return web.json_response({"error": "No video enqueued yet"}, status=404)

        player = MediaPlayer(str(self.latest_video_path))

        if player.video:
            logger.info("✅ Adding video track")
            pc.addTrack(player.video)
        else:
            logger.warning("⚠️ No video track found")

        if player.audio:
            logger.info("✅ Adding audio track")
            pc.addTrack(player.audio)
        else:
            logger.warning("⚠️ No audio track found")

        await pc.setRemoteDescription(offer)
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)

        async def cleanup():
            await player.stop()
            await pc.close()
            self.webpcs.remove(pc)

        asyncio.create_task(self._watch_connection(pc, cleanup))

        return web.json_response({
            "sdp": pc.localDescription.sdp,
            "type": pc.localDescription.type
        })

    async def _watch_connection(self, pc: RTCPeerConnection, cleanup_callback):
        # Wait until connection closes
        while pc.connectionState != "closed":
            await asyncio.sleep(1)
        await cleanup_callback()


    async def webrtc_answer(self, request):
        return web.json_response({"status": "ok"})

    async def start_server(self):
        app = await self.create_http_server()
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, self.host, self.port)
        await site.start()
        logger.info(f"🚀 WebRTC server running at http://{self.host}:{self.port}")
        return runner
