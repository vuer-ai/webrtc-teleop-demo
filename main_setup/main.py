import os
from asyncio import sleep

from numpy import arcsin, arctan2, array, rad2deg
from vuer import Vuer, VuerSession
from vuer.schemas import AmbientLight, DirectionalLight, Hands, MotionControllers, Movable, PointLight, Scene, WebRTCVideoPlane

VUER_DEV_URI = os.environ["VUER_DEV_URI"]
VUER_HOST = os.environ.get("VUER_HOST", "localhost")
# needs to be https to work in webXR
WEBRTC_URI = os.environ.get("WEBRTC_URI", "http://localhost:8080/offer")

app = Vuer(static_root=".")

print("connect via", f"{VUER_DEV_URI}?ws=wss://{VUER_HOST}")
print("connect to webrtc server via", WEBRTC_URI)

@app.add_handler("OBJECT_MOVE")
async def handler(event, session):
    print(f"Movement Event: key-{event.key}", event.value)
    # pass

@app.spawn(start=True)
async def main(sess: VuerSession):

    quad = WebRTCVideoPlane(
        src=WEBRTC_URI,
        key="video-quad",
        # position=[0, 1, -3],
        height=1,
        aspect=16/9,
        fixed=True,
    )

    quad_with_handle = Movable( quad, key="camera_front", position=[0, 1, -3], offset=[0, -9/16, 0], handle=[0.8, 0.05, 0.05],)
    sess.set @ Scene(
        quad_with_handle,
        frameloop='always',
        bgChildren=[
            Hands( stream=True, key="hands-demo", fps=25 ),
            MotionControllers( stream="stream", key="controller-demo", fps=25 ),
        ]
    )
    await sleep(0.01)

    sess.upsert @ Hands(key='hands-demo')
    sess.upsert @ MotionControllers(key='controller-demo')
    sess.upsert @ Movable(key='left', position=[0.15, 1.1, -0.3], localRotation=True, quaternion=[-0.7, 0, 0.7, 0])
    sess.upsert @ Movable(key='right', position=[-0.15, 1.1, -0.3], localRotation=True, quaternion=[-0.7, 0, 0.7, 0])

    # Calculate Euler angles for the directional light direction vector
    def to_euler(direction):
        x, y, z = array(direction) / (sum(array(direction) ** 2) ** 0.5)  # Normalize the vector
        yaw = rad2deg(arctan2(y, x))  # Calculate yaw
        pitch = rad2deg(arcsin(z))  # Calculate pitch
        roll = 0.0  # Assuming no roll for a direction vector
        return [yaw, pitch, roll]

    sess.upsert @ DirectionalLight(key="key-light", position=[1, 0.5, -0.5], rotation=to_euler([-1, -0.5, 0.5]))
    sess.upsert @ DirectionalLight(key='fill-light', position=[0.8, 0.4, 0.7], rotation=to_euler([-0.8, -0.6, -0.5]))
    sess.upsert @ AmbientLight(key="ambient", intensity=0.25)
    sess.upsert @ PointLight(key="spot", intensity=1, position=[0, 1, 1])

    while True:
        await sleep(1000.0)