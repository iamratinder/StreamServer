"""
Real-time Media Streaming Server for Digital Human Pipeline Testing

This server provides WebRTC-compatible endpoints for streaming
audio and video files. It includes performance monitoring and a modular architecture.
"""

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
    # Create server instance
    server = MediaStreamingServer(host='localhost', port=8765)

    # Start only the HTTP/WebRTC server
    http_runner = await server.start_server()

    try:
        logger.info("Server is running. Press Ctrl+C to stop.")
        await asyncio.Future()  # Run forever
    except KeyboardInterrupt:
        logger.info("Shutting down server...")
    finally:
        await http_runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())