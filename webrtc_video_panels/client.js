var pc = null;

function negotiate() {
  pc.addTransceiver('video', {direction: 'recvonly'});
  pc.addTransceiver('audio', {direction: 'recvonly'});
  return pc.createOffer().then((offer) => {
    return pc.setLocalDescription(offer);
  }).then(() => {
    // wait for ICE gathering to complete
    return new Promise((resolve) => {
      if (pc.iceGatheringState === 'complete') {
        console.log("ICE GATHERING COMPLETE");
        resolve();
      } else {
        console.log("ICE GATHERING NOT COMPLETE");
        const checkState = () => {
          if (pc.iceGatheringState === 'complete') {
            console.log("ICE GATHERING COMPLETE");
            pc.removeEventListener('icegatheringstatechange', checkState);
            resolve();
          }
        };
        pc.addEventListener('icegatheringstatechange', checkState);
      }
    });
  }).then(() => {
    var offer = pc.localDescription;
    var queries = new URLSearchParams(window.location.search);
    var uri = queries.get('uri') || "/offer";
    console.info("trying to connect to", uri)
    return fetch(uri, {
      body: JSON.stringify({
        sdp: offer.sdp,
        type: offer.type,
      }),
      headers: {
        'Content-Type': 'application/json'
      },
      method: 'POST'
    });
  }).then((response) => {
    console.log("RESPONSE", response);
    return response.json();
  }).then((answer) => {
    console.log("remote answer", answer);
    return pc.setRemoteDescription(answer);
  }).catch((e) => {
    alert(e);
  });
}

function start() {
  var config = {
    sdpSemantics: 'unified-plan'
  };

  if (document.getElementById('use-stun').checked) {
    config.iceServers = [{urls: ['stun:stun.l.google.com:19302']}];
  }

  pc = new RTCPeerConnection(config);

  // connect audio / video
  pc.addEventListener('track', (evt) => {
    if (evt.track.kind == 'video') {
      document.getElementById('video').srcObject = evt.streams[0];
    } else {
      document.getElementById('audio').srcObject = evt.streams[0];
    }
  });

  document.getElementById('start').style.display = 'none';
  negotiate();
  document.getElementById('stop').style.display = 'inline-block';
}

function stop() {
  document.getElementById('stop').style.display = 'none';

  // close peer connection
  setTimeout(() => {
    pc.close();
  }, 500);
}
