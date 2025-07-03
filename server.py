import asyncio
import json
import logging
import os
from pathlib import Path
from typing import List, Optional
from aiohttp import web
import aiohttp
from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaPlayer
import aiohttp_cors

logger = logging.getLogger("media.server")
logging.basicConfig(level=logging.INFO)

class MediaStreamingServer:
    def __init__(self, host='0.0.0.0', port=8765, media_dir='./videos'):
        self.host = host
        self.port = port
        self.media_dir = Path(media_dir)
        self.media_dir.mkdir(parents=True, exist_ok=True)
        self.latest_video_url: Optional[str] = None
        self.webpcs: List[RTCPeerConnection] = []

    async def create_http_server(self):
        app = web.Application()
        app["server"] = self

        # Add endpoints
        app.router.add_get('/health', self.health_check)
        app.router.add_post('/enqueue-video', self.enqueue_video)
        app.router.add_post('/webrtc/offer', self.webrtc_offer)
        app.router.add_post('/webrtc/answer', self.webrtc_answer)

        # Add CORS
        cors = aiohttp_cors.setup(app, defaults={
            "http://localhost:3000": aiohttp_cors.ResourceOptions(
                allow_credentials=True,
                expose_headers="*",
                allow_headers="*"
            ),
            "*": aiohttp_cors.ResourceOptions(
                allow_credentials=True,
                expose_headers="*",
                allow_headers="*"
            )
        })

        # Attach CORS to all routes
        for route in list(app.router.routes()):
            cors.add(route)


        return app
    
    async def health_check(self, request):
        return web.json_response({"status": "ok", "message": "Server is healthy."})


    async def enqueue_video(self, request):
        data = await request.json()
        url = data.get("url")

        if not url:
            return web.json_response({"error": "Missing 'url'"}, status=400)

        self.latest_video_url = url
        logger.info(f"✅ Video URL enqueued: {url}")
        return web.json_response({"message": "Video URL enqueued successfully"})


    async def webrtc_offer(self, request):
        params = await request.json()
        offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])
        pc = RTCPeerConnection()
        self.webpcs.append(pc)

        if not self.latest_video_url:
            return web.json_response({"error": "No video URL enqueued yet"}, status=404)

        try:
            player = MediaPlayer(self.latest_video_url, format='mp4')  # or auto-detect
        except Exception as e:
            logger.error(f"❌ Failed to create MediaPlayer from URL: {e}")
            return web.json_response({"error": "Invalid media URL or ffmpeg issue"}, status=500)

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
            if pc in self.webpcs:
                self.webpcs.remove(pc)

        asyncio.create_task(self._watch_connection(pc, cleanup))

        return web.json_response({
            "sdp": pc.localDescription.sdp,
            "type": pc.localDescription.type
        })

    async def _watch_connection(self, pc: RTCPeerConnection, cleanup_callback):
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