import os
import asyncio
import logging
from server import MediaStreamingServer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Main function for testing the streaming server."""

    # ✅ Get port from environment (Render sets PORT)
    port = int(os.environ.get("PORT", 10000))

    # ✅ Bind to 0.0.0.0 so Render can access it
    server = MediaStreamingServer(host='0.0.0.0', port=port)

    http_runner = await server.start_server()

    try:
        logger.info(f"🚀 WebRTC server running at http://0.0.0.0:{port}")
        logger.info("Server is running. Press Ctrl+C to stop.")
        await asyncio.Future()  # Run forever
    except KeyboardInterrupt:
        logger.info("Shutting down server...")
    finally:
        await http_runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
