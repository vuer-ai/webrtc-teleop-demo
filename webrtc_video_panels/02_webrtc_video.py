"""
1. launch this server
2. set up a ngrok link to this server
3. launch the rtc_server.py
4. set up a ngrok link to the rtc_server.py

"""
from asyncio import sleep

from dotvar import auto_load  # noqa
from vuer import Vuer, VuerSession
from vuer.schemas import Scene, WebRTCVideoPlane

app = Vuer(host="0.0.0.0", cors_origins="https://{VUER_NGROK_PREFIX}-dev.ngrok.app", static_root=".")

@app.spawn(start=True)
async def main(sess: VuerSession):

    quad = WebRTCVideoPlane(
        src="https://ge-webrtc.ngrok.app/offer",
        key="video-quad",
        # you can remove this to fill the entire screen.
        aspect=16/9,
    )
    sess.set @ Scene(bgChildren=[quad], frameloop='always')

    while True:
        await sleep(1000.0)