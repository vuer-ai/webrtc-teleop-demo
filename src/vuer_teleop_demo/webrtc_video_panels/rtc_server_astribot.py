import asyncio
import json
import logging
import os
import platform
import ssl
from queue import Queue

import aiohttp_cors
import cv2
import numpy as np
from aiohttp import web
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack
from aiortc.contrib.media import MediaPlayer, MediaRelay
from aiortc.rtcrtpsender import RTCRtpSender
from av import VideoFrame

ROOT = os.path.dirname(__file__)

relay = None
webcam = None

# Global queue for ROS frames
frame_queue = Queue(maxsize=2)  # Small queue to keep latency low


class ROSVideoTrack(VideoStreamTrack):
    """
    Custom video track that reads frames from ROS callback
    """
    def __init__(self):
        super().__init__()
        self.frame_queue = frame_queue

    async def recv(self):
        """
        Receive the next video frame
        """
        try:
            # Check if frame is available
            if not self.frame_queue.empty():
                img = self.frame_queue.get_nowait()

                # Convert numpy array to VideoFrame
                # Assuming img is BGR format from ROS (cv_bridge)
                frame = VideoFrame.from_ndarray(img, format='bgr24')
                frame.pts, frame.time_base = await self.next_timestamp()
                return frame
            else:
                # If no frame available, wait a bit and try again
                await asyncio.sleep(0.01)
                return await self.recv()
        except Exception as e:
            print(f"Error receiving frame: {e}")
            # Return a black frame on error
            img = np.zeros((720, 1280, 3), dtype=np.uint8)
            frame = VideoFrame.from_ndarray(img, format='bgr24')
            frame.pts, frame.time_base = await self.next_timestamp()
            return frame


def ros_image_callback(topic_name, msg, width, height, array: np.ndarray):
    """
    Callback function for Astribot image subscriber.
    This matches the signature expected by astribot.register_image_callback()

    Args:
        topic_name: Name of the image topic
        msg: Message metadata
        width: Image width
        height: Image height
        array: numpy array in BGR format (when need_decode=True)
    """
    import cv2
    try:
        if msg.format.lower() == "jpeg":
            # Drop old frames if queue is full (keep only latest)
            if frame_queue.full():
                try:
                    frame_queue.get_nowait()
                except:
                    pass
            frame_queue.put_nowait(array)
            # print(len(frame_queue.queue), array.shape)
    except Exception as e:
        print(f"Error queuing frame: {e}")


def create_local_tracks(play_from, decode, device: str = None, format: str = None, use_ros: bool = False):
    global relay, webcam

    if use_ros:
        # Return custom ROS video track
        print("Using ROS video source")
        return None, ROSVideoTrack()

    if play_from:
        print(f"Playing from file: {play_from}")
        player = MediaPlayer(play_from, decode=decode)
        return player.audio, player.video

    options = {"framerate": "30", "video_size": "1280x720"}
    if relay is None:
        if platform.system() == "Darwin":
            format = format or "avfoundation"
            webcam = MediaPlayer(
                "default:none", format=format, options=options
            )
        elif platform.system() == "Windows":
            format = format or "dshow"
            webcam = MediaPlayer(
                "video=Integrated Camera", format=format, options=options
            )
        else:
            format = format or "v4l2"
            webcam = MediaPlayer(device, format=format, options=options)

        relay = MediaRelay()
    return None, relay.subscribe(webcam.video)


def force_codec(pc, sender, forced_codec):
    kind = forced_codec.split("/")[0]
    codecs = RTCRtpSender.getCapabilities(kind).codecs
    transceiver = next(t for t in pc.getTransceivers() if t.sender == sender)
    transceiver.setCodecPreferences(
        [codec for codec in codecs if codec.mimeType == forced_codec]
    )


async def index(request):
    content = open(os.path.join(ROOT, "index.html"), "r").read()
    return web.Response(content_type="text/html", text=content)


async def javascript(request):
    content = open(os.path.join(ROOT, "client.js"), "r").read()
    return web.Response(content_type="application/javascript", text=content)


async def offer(request):
    params = await request.json()
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

    pc = RTCPeerConnection()
    pcs.add(pc)

    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        print("Connection state is %s" % pc.connectionState)
        if pc.connectionState == "failed":
            await pc.close()
            pcs.discard(pc)

    # open media source
    audio, video = create_local_tracks(
        Args.filename,
        decode=not Args.play_without_decoding,
        device=Args.device,
        format=Args.format,
        use_ros=Args.use_ros
    )

    if audio:
        audio_sender = pc.addTrack(audio)
        if Args.audio_codec:
            force_codec(pc, audio_sender, Args.audio_codec)
        elif Args.play_without_decoding:
            raise Exception("You must specify the audio codec using --audio-codec")

    if video:
        video_sender = pc.addTrack(video)
        if Args.video_codec:
            force_codec(pc, video_sender, Args.video_codec)
        elif Args.play_without_decoding:
            raise Exception("You must specify the video codec using --video-codec")

    await pc.setRemoteDescription(offer)

    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return web.Response(
        content_type="application/json",
        text=json.dumps(
            {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}
        ),
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Allow-Credentials": "true"
        }
    )


async def offer_options(request):
    return web.Response(
        status=204,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Allow-Credentials": "true"
        }
    )


pcs = set()


async def on_shutdown(app):
    # close peer connections
    coros = [pc.close() for pc in pcs]
    await asyncio.gather(*coros)
    pcs.clear()


from params_proto import Flag, ParamsProto, Proto


class Args(ParamsProto):
    description = "WebRTC webcam demo with ROS support"
    cert_file = Proto(help="SSL certificate file (for HTTPS)")
    key_file = Proto(help="SSL key file (for HTTPS)")

    host = Proto("0.0.0.0", help="Host for HTTP server (default: 0.0.0.0)")
    port = Proto(default=8080, dtype=int, help="Port for HTTP server (default: 8080)")
    cors = Proto("https://vuer.ai", env="https://vuer.ai,https://$VUER_HOST", help="CORS origin to allow")

    device = Proto(help="/dev/video* device, you can find this via ")
    format = Proto(help="format for the video code, specific to the device hardware.")
    filename = Proto(help="Read the media from a file and send it.")
    play_without_decoding = Flag(
        "Read the media without decoding it (experimental). "
        "For now it only works with an MPEGTS container with only H.264 video."
    )

    use_ros = Flag("Use ROS image topic as video source instead of webcam or file")

    audio_codec = Proto(help="Force a specific audio codec (e.g. audio/opus)")
    video_codec = Proto(help="Force a specific video codec (e.g. video/H264)")

    verbose = Flag()


if __name__ == "__main__":

    print("Set up the environment variable VUER_DEV_URI. This needs to be a public IP.")
    print("to connect from webXR, you need to have STL/SSL enabled. Follow the instruction here:")
    print("link: https://letsencrypt.org/getting-started/")

    from core.astribot_api.astribot_client import Astribot

    astribot = Astribot()
    astribot.activate_camera()

    target_camera = "head_rgbd"
    # check if head_rgbd camera is already activated
    cameras_stat = astribot.get_cameras_info()
    if cameras_stat[target_camera]["activate"] != True:
        total_seconds = 10
        print(f"Waiting for camera module activate for {total_seconds} seconds ", end="", flush=True)

        for _ in range(total_seconds):
            cameras_stat = astribot.get_cameras_info()
            if cameras_stat[target_camera]["activate"] == True:
                break
            print(".", end="", flush=True)

        print("\n Waiting end!")

    # get cameras activate state
    cameras_stat = astribot.get_cameras_info()
    print(f"cameras status: {cameras_stat}")

    if cameras_stat[target_camera]["activate"] != True:
        print(f"Can not activate camera {target_camera}")
        os._exit(1)

    calib_paras = astribot.get_cameras_calibration_parameter()
    print(f"camera calibration parameter: {calib_paras}")

    # register as a subscriber to get real-time image of head
    subscriber = astribot.register_image_callback(target_camera, "color", ros_image_callback, need_decode=True)

    print(f"now connect to: https://{Args.host}:{Args.port}")

    if Args.verbose:
        import pprint

        pp = pprint.PrettyPrinter(indent=4)
        print("Arguments:")
        pp.pprint(vars(Args))

    else:
        logging.basicConfig(level=logging.INFO)

    if Args.cert_file:
        ssl_context = ssl.SSLContext()
        ssl_context.load_cert_chain(Args.cert_file, Args.key_file)
    else:
        ssl_context = None

    app = web.Application()
    cors = aiohttp_cors.setup(
        app,
        defaults={
            Args.cors: aiohttp_cors.ResourceOptions(
                allow_credentials=True,
                expose_headers="*",
                allow_headers="*",
                allow_methods="*",
            )
        },
    )

    app.on_shutdown.append(on_shutdown)
    app.router.add_get("/", index)
    app.router.add_get("/client.js", javascript)
    app.router.add_post("/offer", offer)
    app.router.add_options("/offer", offer_options)

    web.run_app(app, host=Args.host, port=Args.port, ssl_context=ssl_context)
