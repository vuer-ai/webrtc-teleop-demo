from asyncio import sleep

from vuer import Vuer, VuerSession
from vuer.schemas import MotionControllers

app = Vuer()

@app.add_handler("CONTROLLER_MOVE")
async def handler(event, session):
    print(f"Movement Event: key-{event.key}", event.value)
    # pass


@app.spawn(start=True)
async def main(session: VuerSession):
    # Important: You need to set the `stream` option to `True` to start
    # streaming the hand movement.

    session.upsert(
        MotionControllers(
            stream="stream",
            key="controller-demo",
            fps=0.1,
        ),
        to="bgChildren",
    )

    while True:
        await sleep(10000.0)