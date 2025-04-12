from asyncio import sleep

from vuer import Vuer, VuerSession
from vuer.schemas import Hands

app = Vuer()

@app.add_handler("HAND_MOVE")
async def handler(event, session):
    # print(f"Movement Event: key-{event.key}", event.value)
    pass



@app.spawn(start=True)
async def main(session: VuerSession):
    # Important: You need to set the `stream` option to `True` to start
    # streaming the hand movement.

    session.upsert(
        Hands(
            stream=True,
            key="hands-demo",
            # hideLeft=True,       # hides the hand, but still streams the data.
            # hideRight=True,      # hides the hand, but still streams the data.
            # disableLeft=True,    # disables the left data stream, also hides the hand.
            # disableRight=True,   # disables the right data stream, also hides the hand.
        ),
        to="bgChildren",
    )

    while True:
        await sleep(10000.0)