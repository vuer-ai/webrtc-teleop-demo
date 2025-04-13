"""
1. launch this server
2. set up a ngrok link to this server
3. launch the rtc_server.py
4. set up a ngrok link to the rtc_server.py


--Vuer.cert /etc/letsencrypt/live/fourier.csail.mit.edu/fullchain.pem
--Vuer.key /etc/letsencrypt/live/fourier.csail.mit.edu/privkey.pem
--Vuer.port=9000
--Vuer.host="fourier.csail.mit.edu"
# --Vuer.cors="https://vuer.ai"
"""
from asyncio import sleep

from dotvar import auto_load  # noqa
from vuer import Vuer, VuerSession
from vuer.schemas import Scene, WebRTCVideoPlane

app = Vuer(host="fourier.csail.mit.edu", static_root=".")

@app.spawn(start=True)
async def main(sess: VuerSession):

    quad = WebRTCVideoPlane(
        src="https://fourier.csail.mit.edu:8080/offer",
        key="video-quad",
        # you can remove this to fill the entire screen.
        aspect=16/9,
    )
    sess.set @ Scene(bgChildren=[quad], frameloop='always')

    while True:
        await sleep(1000.0)