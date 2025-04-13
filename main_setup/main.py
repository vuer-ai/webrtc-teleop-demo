from asyncio import sleep

from vuer import Vuer, VuerSession
from vuer.schemas import Hands, MotionControllers, Scene, WebRTCVideoPlane

app = Vuer(host="fourier.csail.mit.edu", static_root=".")

@app.add_handler("CONTROLLER_MOVE")
async def handler(event, session):
    print(f"Movement Event: key-{event.key}", event.value)
    # pass

@app.add_handler("HAND_MOVE")
async def handler(event, session):
    print(f"Movement Event: key-{event.key}", event.value)
    # pass


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
    sess.set @ Scene(quad, frameloop='always', bgChildren=[
        Hands(
            stream=True,
            key="hands-demo",
            fps=25,
        ),
        MotionControllers(
            stream="stream",
            key="controller-demo",
            fps=25,
        ),
    ])

    while True:
        await sleep(1000.0)