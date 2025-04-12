from asyncio import sleep

from vuer import Vuer, VuerSession
from vuer.schemas import Hands, MotionControllers

app = Vuer()

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
            fps=0.1,
        ),
        to="bgChildren",
    )
    session.upsert(
        MotionControllers(
            stream="stream",
            key="motioncontroller-demo",
            fps=0.1,
        ),
        to="bgChildren",
    )

    while True:
        await sleep(10000.0)