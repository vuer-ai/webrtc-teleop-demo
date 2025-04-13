from asyncio import sleep

from vuer import Vuer, VuerSession
from vuer.schemas import Scene, WebRTCVideoPlane

app = Vuer(host="fourier.csail.mit.edu", static_root=".")

@app.spawn(start=True)
async def main(sess: VuerSession):

    quad = WebRTCVideoPlane(
        src="https://fourier.csail.mit.edu:8080/offer",
        key="video-quad",
        height=1,
        aspect=16/9,
        fixed=True,
        position=[0, 1, -3]
    )
    sess.set @ Scene(quad, frameloop='always')

    while True:
        await sleep(1000.0)