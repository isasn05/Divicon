const video = document.getElementById("video");

navigator.mediaDevices
    .getUserMedia({ video: true })
    .then(stream => {
        video.srcObject = stream;
    });