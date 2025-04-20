import os
from asyncio import sleep

from vuer import Vuer, VuerSession
from vuer.schemas import Scene, WebRTCVideoPlane

VUER_HOST = os.environ.get("VUER_HOST", "localhost")
WEBRTC_SERVER_URI = os.environ.get("WEBRTC_SERVER_URI", "http://localhost:8080/offer")

app = Vuer(host=VUER_HOST, static_root=".")

print("connect via", VUER_HOST + "?ws=wss://" + VUER_HOST.split("//")[1] + "")

@app.spawn(start=True)
async def main(sess: VuerSession):

    quad = WebRTCVideoPlane(
        src=WEBRTC_SERVER_URI,
        key="video-quad",
        height=1,
        aspect=16/9,
        fixed=True,
        position=[0, 1, -3]
    )
    sess.set @ Scene(quad, frameloop='always')

    while True:
        await sleep(1000.0)