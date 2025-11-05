from asyncio import sleep

from vuer import Vuer, VuerSession
from vuer.schemas import Scene, StereoVideoPlane

app = Vuer(host="0.0.0.0", cors_origins="*", static_root=".")

@app.spawn(start=True)
async def show_heatmap(sess: VuerSession):
    sess.set @ Scene(
        frameloop='always',
        bgChildren=[
            StereoVideoPlane(
                src="http://localhost:8012/static/MaryOculus.mp4",
                height=1024,
                width=768,
            ),
        ]
    )

    while True:
        await sleep(1000.0)
