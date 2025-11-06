"""
Example of using WebRTC camera stream with Vuer.
This connects to the rtc_server_ros.py WebRTC server.
"""
from asyncio import sleep

from vuer import Vuer, VuerSession
from vuer.schemas import Scene, WebRTCVideoPlane, Sphere, ImageBackground
import numpy as np

# Create Vuer app (nginx handles SSL, so no certs needed here)
app = Vuer(
    host="0.0.0.0",
    port=8013,  # nginx will proxy from 8443 to this port
)


@app.spawn(start=True)
async def show_webrtc_stream(sess: VuerSession):
    """
    Display WebRTC stream from rtc_server_ros.py in Vuer
    """
    quad = WebRTCVideoPlane(
        # Point to your WebRTC server's /offer endpoint
        # Make sure rtc_server_ros.py is running on this address
        src="https://192.168.2.27:8080/offer",

        key="video-quad",

        # Set aspect ratio (adjust based on your camera)
        aspect=16/9,  # Common for most cameras

        # Height in VR space (in meters)
        height=1,

        # Optional: fix position relative to camera
        fixed=True,

        # Position in 3D space [x, y, z] in meters
        position=[5, 1, 0],
        rotation=[0, -np.pi/2, 0],
    )

    background = ImageBackground(

                # Can scale the images down.
                np.zeros((369, 640, 3), dtype=np.uint8),

                # One of ['b64png', 'png', 'b64jpeg', 'jpeg']
                # 'b64png' does not work for some reason, but works for the nerf demo.
                # 'jpeg' encoding is significantly faster than 'png'.
                format="jpeg",
                quality=20,
                key="background",
                fixed=True,
                distanceToCamera=1,

                # can test with matrix
                # matrix=[
                #     1.2418025750411799, 0, 0, 0,
                #     0, 1.5346539759579207, 0, 0,
                #     0, 0, 1, 0,
                #     0, 0, -3, 1,
                # ],
                position=[5, 3, 0],
                ### Can also rotate the plane in-place.
                rotation=[0, -np.pi/2, 0],
            )

    sess.set @ Scene(
        Sphere(args=[0.1, 10, 10]),
        quad,
        background,
        frameloop='always',
    )

    # Keep the session alive
    while True:
        await sleep(1)

#
# if __name__ == "__main__":
#     # Run on port 8012 (different from WebRTC server port 8080)
#     app.run(port=8013)
