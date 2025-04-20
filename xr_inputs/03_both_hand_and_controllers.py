import os
from asyncio import sleep
from dotvar import auto_load  # noqa

from main_setup.main import VUER_DEV_URI
from vuer import Vuer, VuerSession
from vuer.schemas import Hands, MotionControllers

VUER_HOST = os.environ.get("VUER_HOST", "localhost")
VUER_DEV_URI = os.environ.get("VUER_DEV_URI", f"https://{VUER_HOST}/editor?ws=wss://{VUER_DEV_URI}")
WEBRTC_SERVER_URI = os.environ.get("WEBRTC_SERVER_URI", "http://localhost:8080/offer")

app = Vuer(host="0.0.0.0", static_root=".")

print("connect via", f"https://{VUER_HOST}/editor?ws=wss://{VUER_HOST}")

@app.add_handler("CONTROLLER_MOVE")
async def handler(event, session):
    print(f"Movement Event: key-{event.key}", event.value)
    # pass

@app.add_handler("HAND_MOVE")
async def handler(event, session):
    print(f"Movement Event: key-{event.key}", event.value)
    # pass


@app.spawn(start=True)
async def main(session: VuerSession):
    # Important: You need to set the `stream` option to `True` to start
    # streaming the hand movement.

    session.upsert(
        Hands(
            stream=True,
            key="hands-demo",
            fps=25,
        ),
        to="bgChildren",
    )
    session.upsert(
        MotionControllers(
            stream="stream",
            key="controller-demo",
            fps=25,
        ),
        to="bgChildren",
    )

    while True:
        await sleep(10000.0)