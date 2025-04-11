from asyncio import sleep

from vuer import Vuer, VuerSession
from vuer.schemas import Scene, WebRTCVideoPlane

app = Vuer(host="0.0.0.0", cors_origins="*", static_root=".")

@app.spawn(start=True)
async def main(sess: VuerSession):

    quad = WebRTCVideoPlane(
        src="https://ge-webrtc.ngrok.app/offer",
        key="video-quad",
        # you can remove this to fill the entire screen.
        aspect=16/9,
    )
    sess.set @ Scene(bgChildren=[quad])

    while True:
        await sleep(1000.0)