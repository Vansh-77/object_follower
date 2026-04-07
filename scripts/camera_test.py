from flask import Flask, Response
import cv2
import threading
import time

app = Flask(__name__)

# -------- Camera --------
cam = cv2.VideoCapture(0, cv2.CAP_V4L2)
cam.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
cam.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
cam.set(cv2.CAP_PROP_FPS, 15)

frame = None

# -------- Camera Thread --------
def camera_thread():
    global frame
    while True:
        success, img = cam.read()
        if success:
            frame = img

threading.Thread(target=camera_thread, daemon=True).start()

time.sleep(2)  # warmup

# -------- Generator --------
def generate():
    global frame
    while True:
        if frame is None:
            continue

        _, buffer = cv2.imencode('.jpg', frame)
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' +
               buffer.tobytes() + b'\r\n')

        time.sleep(0.03)

# -------- Routes --------
@app.route('/')
def index():
    return '<img src="/video">'

@app.route('/video')
def video():
    return Response(generate(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

# -------- Run --------
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, threaded=True)
