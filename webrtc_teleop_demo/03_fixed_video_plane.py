from asyncio import sleep

from vuer import Vuer, VuerSession
from vuer.schemas import Scene, WebRTCVideoPlane

app = Vuer(host="0.0.0.0", cors_origins="*", static_root=".")

@app.spawn(start=True)
async def main(sess: VuerSession):

    quad = WebRTCVideoPlane(
        src="https://ge-webrtc.ngrok.app/offer",
        key="video-quad",
        height=1,
        aspect=16/9,
        fixed=True,
        position=[0, 1, -8]
    )
    sess.set @ Scene(quad)

    while True:
        await sleep(1000.0)