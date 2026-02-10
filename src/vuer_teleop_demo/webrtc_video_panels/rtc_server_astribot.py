import asyncio
import json
import logging
import os
import platform
import ssl
from queue import Queue

import aiohttp_cors
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

# Storage for multi-camera stitching
import threading
import cv2

camera_frames = {
    "head_rgbd": None,
    "left_wrist_rgbd": None,
    "right_wrist_rgbd": None,
}
camera_frames_lock = threading.Lock()
camera_frame_counts = {"head_rgbd": 0, "left_wrist_rgbd": 0, "right_wrist_rgbd": 0}

# Global reference to astribot client (set in main) - use dict for mutability
_globals = {"astribot_client": None}


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
            # Wait for a frame with a loop (not recursion to avoid stack overflow)
            while self.frame_queue.empty():
                await asyncio.sleep(0.01)

            img = self.frame_queue.get_nowait()

            # Convert numpy array to VideoFrame
            # Assuming img is BGR format from ROS (cv_bridge)
            frame = VideoFrame.from_ndarray(img, format='bgr24')
            frame.pts, frame.time_base = await self.next_timestamp()
            return frame
        except Exception as e:
            print(f"Error receiving frame: {e}")
            # Return a black frame on error
            img = np.zeros((720, 1280, 3), dtype=np.uint8)
            frame = VideoFrame.from_ndarray(img, format='bgr24')
            frame.pts, frame.time_base = await self.next_timestamp()
            return frame


def ros_image_callback(topic_name, msg, width, height, array: np.ndarray):
    """
    Callback function for Astribot image subscriber (single camera mode).
    This matches the signature expected by astribot.register_image_callback()

    Args:
        topic_name: Name of the image topic
        msg: Message metadata
        width: Image width
        height: Image height
        array: numpy array in BGR format (when need_decode=True)
    """
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


def unified_stitch_callback(topic_name, msg, width, height, array: np.ndarray):
    """
    Single unified callback for all cameras (matches SDK pattern).
    Uses topic_name to identify which camera the frame is from.
    """
    try:
        astribot_client = _globals.get("astribot_client")
        if msg.format.lower() == "jpeg" and astribot_client is not None:
            # Get camera name from topic (SDK method)
            camera_name = astribot_client.get_camera_name_from_topic_name(topic_name)

            if camera_name in camera_frames:
                camera_frame_counts[camera_name] += 1
                if camera_frame_counts[camera_name] % 100 == 1:
                    print(f"[RTC] {camera_name}: received frame {camera_frame_counts[camera_name]}, shape={array.shape}")

                with camera_frames_lock:
                    camera_frames[camera_name] = array.copy()
    except Exception as e:
        print(f"Error in unified stitch callback: {e}")


def make_stitched_callback(camera_name: str, stitch_target_height: int = 480):
    """
    Factory function to create a callback for a specific camera that participates in stitching.
    DEPRECATED: Use unified_stitch_callback instead for better compatibility.
    """
    frame_count = [0]

    def callback(topic_name, msg, width, height, array: np.ndarray):
        try:
            if msg.format.lower() == "jpeg":
                frame_count[0] += 1
                if frame_count[0] % 100 == 1:
                    print(f"[RTC] {camera_name}: received frame {frame_count[0]}, shape={array.shape}")

                with camera_frames_lock:
                    camera_frames[camera_name] = array.copy()
        except Exception as e:
            print(f"Error in stitched callback for {camera_name}: {e}")
    return callback


_stitch_log_counter = [0]
_stitch_thread_running = False


def start_stitch_thread(target_height: int = 480, fps: int = 30):
    """Start a background thread that stitches frames at a fixed rate."""
    global _stitch_thread_running
    _stitch_thread_running = True

    def stitch_loop():
        import time
        interval = 1.0 / fps
        while _stitch_thread_running:
            stitch_and_queue_frames(target_height)
            time.sleep(interval)

    thread = threading.Thread(target=stitch_loop, daemon=True)
    thread.start()
    print(f"[RTC] Started stitch thread at {fps} FPS")
    return thread


def stitch_and_queue_frames(target_height: int = 480):
    """
    Stitch all available camera frames together.
    Layout:
        +------------------+
        |      HEAD        |
        |   (full width)   |
        +--------+---------+
        | LEFT   | RIGHT   |
        | (0.5x) | (0.5x)  |
        +--------+---------+
    Head is scaled to target_height, wrists are downsampled by 2x and placed below.
    """
    head = camera_frames.get("head_rgbd")
    left = camera_frames.get("left_wrist_rgbd")
    right = camera_frames.get("right_wrist_rgbd")

    # Need at least head to show anything meaningful
    if head is None:
        return

    _stitch_log_counter[0] += 1
    if _stitch_log_counter[0] % 100 == 1:  # Log every 100 stitches
        print(f"[RTC] Stitching: head={head.shape if head is not None else None}, "
              f"left={left.shape if left is not None else None}, "
              f"right={right.shape if right is not None else None}")

    # Scale head to target height (ensure even width for clean split)
    h, w = head.shape[:2]
    scale = target_height / h
    head_width = int(w * scale)
    # Make head_width even so wrists split evenly
    head_width = head_width - (head_width % 2)
    head_scaled = cv2.resize(head, (head_width, target_height))

    # Wrist row: each wrist is half the head width, half the head height
    wrist_width = head_width // 2
    wrist_height = target_height // 2

    # Prepare wrist images (downsampled by 2x relative to head)
    if left is not None:
        left_scaled = cv2.resize(left, (wrist_width, wrist_height))
    else:
        # Black placeholder if left wrist unavailable
        left_scaled = np.zeros((wrist_height, wrist_width, 3), dtype=np.uint8)

    if right is not None:
        right_scaled = cv2.resize(right, (wrist_width, wrist_height))
    else:
        # Black placeholder if right wrist unavailable
        right_scaled = np.zeros((wrist_height, wrist_width, 3), dtype=np.uint8)

    # Stitch wrists horizontally (guaranteed to match head_width since wrist_width * 2 = head_width)
    wrists_row = np.hstack([left_scaled, right_scaled])

    # Stack head on top, wrists on bottom
    stitched = np.vstack([head_scaled, wrists_row])

    if _stitch_log_counter[0] % 100 == 1:
        print(f"[RTC] Stitched output: {stitched.shape}")

    # Queue the stitched frame
    if frame_queue.full():
        try:
            frame_queue.get_nowait()
        except:
            pass
    frame_queue.put_nowait(stitched)


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
    stitch_cameras = Flag("Stitch head + left_wrist + right_wrist cameras together")
    stitch_height = Proto(default=480, dtype=int, help="Target height for stitched output (default: 480)")

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

    # Determine which cameras to use
    if Args.stitch_cameras:
        target_cameras = ["head_rgbd", "left_wrist_rgbd", "right_wrist_rgbd"]
        print(f"[RTC] Stitching cameras: {target_cameras}")
    else:
        target_cameras = ["head_rgbd"]

    # Wait for cameras to activate
    cameras_stat = astribot.get_cameras_info()
    for target_camera in target_cameras:
        if cameras_stat[target_camera]["activate"] != True:
            total_seconds = 10
            print(f"Waiting for {target_camera} to activate for {total_seconds} seconds ", end="", flush=True)

            for _ in range(total_seconds):
                cameras_stat = astribot.get_cameras_info()
                if cameras_stat[target_camera]["activate"] == True:
                    break
                print(".", end="", flush=True)
                import time
                time.sleep(1)

            print("\n Waiting end!")

    # get cameras activate state
    cameras_stat = astribot.get_cameras_info()
    print(f"cameras status: {cameras_stat}")

    for target_camera in target_cameras:
        activated = cameras_stat.get(target_camera, {}).get("activate", False)
        if activated:
            print(f"[RTC] Camera {target_camera}: ACTIVATED ✓")
        else:
            print(f"[RTC] Camera {target_camera}: NOT ACTIVATED ✗")

    calib_paras = astribot.get_cameras_calibration_parameter()
    print(f"camera calibration parameter: {calib_paras}")

    # Register camera callbacks
    subscribers = []
    if Args.stitch_cameras:
        # Set global astribot client for unified callback
        _globals["astribot_client"] = astribot

        # Register all cameras with the SAME unified callback (SDK pattern)
        for cam in target_cameras:
            sub = astribot.register_image_callback(cam, "color", unified_stitch_callback, need_decode=True)
            if sub:
                subscribers.append(sub)
                print(f"[RTC] Registered unified callback for {cam}")

        # Start background stitch thread (like SDK example)
        start_stitch_thread(target_height=Args.stitch_height, fps=30)
    else:
        # Single camera mode (head only)
        subscriber = astribot.register_image_callback("head_rgbd", "color", ros_image_callback, need_decode=True)
        subscribers.append(subscriber)

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
