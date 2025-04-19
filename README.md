# WebRTC Teleop Demonstration

- **2D Video**
- **Stereo Video**
- **2D WebRTC**
- **Stereo WebRTC**

Others
- **HUD** (moves with the user's head)
- **Stationary Display** (stays at a fixed location)
- **Movable Display**


## Step 1 Verify the RTC Server

```shell
/home/abrashid/anaconda3/bin/conda run -n vuer --no-capture-output \
  python /home/abrashid/mit/webrtc-teleop-demo/webrtc_video_panels/rtc_server.py \
  --cert-file /etc/letsencrypt/live/$MY_DOMAIN/fullchain.pem \
  --key-file /etc/letsencrypt/live/$MY_DOMAIN/privkey.pem \
  --cors https://$MY_DOMAIN \
  --device=/dev/video2 
```

You should be able to click on the "START" button, and see the camera stream.
![figures/rtc_working.png](figures/rtc_working.png)

To see the list of camera devices, do 
![figures/cli_device_list.png](figures/cli_device_list.png)

and you should select to first row for each device.

```shell
v412-ctl --list-devices
```

gives

`
Global Shutter Camera: Global S (usb-0000:0c :00.0-2) :
 /dev/video4
 /dev/video5
 /dev/media2
Global Shutter Camera: Global S (usb-0000:0c: 00.0-3) :
 /dev/video2
 /dev/video3
 /dev/media1
Global Shutter Camera: Global S (usb-0000:0c:00.0-5.2) :
 /dev/video0
 /dev/video1 /dev/mediao
`

