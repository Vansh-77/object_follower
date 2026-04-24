import cv2
import socket
import json
from ultralytics import YOLO
import time
from flask import Flask, Response
import threading

# ---------------- FLASK ----------------
app = Flask(__name__)
stream_frame = None

def generate():
    global stream_frame
    while True:
        if stream_frame is None:
            continue
        _, buffer = cv2.imencode('.jpg', stream_frame)
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
        time.sleep(1/10)

@app.route('/')
def index():
    return '<img src="/video">'

@app.route('/video')
def video():
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

def run_flask():
    app.run(host='0.0.0.0', port=5000)

# threading.Thread(target=run_flask, daemon=True).start()


# ---------------- UDP SETUP ----------------
ESP_IP = "10.210.6.103"
PORT = 5005
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

SEND_INTERVAL = 1.0 / 10  # 10Hz UDP
last_send_time = 0

def send_twist(vx, omega):
    global last_send_time
    current_time = time.time()
    if current_time - last_send_time >= SEND_INTERVAL:
        msg = {"linear": float(vx), "angular": float(omega)}
        sock.sendto(json.dumps(msg).encode(), (ESP_IP, PORT))
        last_send_time = current_time

# ---------------- YOLO ----------------
model = YOLO("yolov8n.pt")

# ---------------- PID ----------------
kp = 0.08
ki = 0.0
kd = 0.001
prev_error = 0
integral = 0
max_speed = 255.0

# ---------------- State ----------------
tracker = None
tracking = False
lost_target_count = 0
max_lost_target = 2

prev_vx = 0
last_cmd = {"linear": 0.0, "angular": 0.0}
last_result = None
frame_count = 0
delay = 1

# ---------------- Camera ----------------
cap = cv2.VideoCapture("../sample_videos/people-detection.mp4")
# for udp stream
# cap = cv2.VideoCapture("udp://@:5000",cv2.CAP_FFMPEG)
# for webcam
# cap = cv2.VideoCapture(0)
# cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
# cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
# cap.set(cv2.CAP_PROP_FPS, 30)
# cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
# for sample video loop
fps = cap.get(cv2.CAP_PROP_FPS)
delay = int(1000 / fps)

while True:
    cap.grab()
    cap.grab()
    ret, frame = cap.retrieve()

    if not ret or frame is None:
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0) # for sample video loop 
        continue

    # frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
    # frame = cv2.resize(frame, (320, 240))
    h, w = frame.shape[:2]
    center_x = w // 2
    center_y = h // 2
    
    cv2.circle(frame, (center_x,center_y), 5, (0, 0, 255), -1)

    vx = 0.0
    omega = 0.0
    
    box = None

# tracking   
    if tracking and tracker is not None:
        success, tracked_box = tracker.update(frame)

        if success:
            x, y, bw, bh = map(int, tracked_box)
            x1, y1 = x, y
            x2, y2 = x + bw, y + bh
            box = (x1, y1, x2, y2)

            cv2.putText(
                frame,
                "TRACKING",
                (x1, y1 - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 255, 0),
                2
            )
        else:
            tracking = False
            tracker = None
            box = None
            
# periodic yolo validation
    detected_boxes = []
    frame_count = (frame_count + 1) % (10 if tracking else 1)

    if frame_count == 0:
        results = model(frame, imgsz=320, verbose=False , classes = [0])[0]
        
        detected_boxes = []
        
        for b in results.boxes:
            x1, y1, x2, y2 = map(int , b.xyxy[0])
            detected_boxes.append((x1, y1, x2, y2))        
        
        if tracking and box is not None:
            tx1 , ty1 , tx2 , ty2 = box 
            matched = False

            for dx1 , dy1 , dx2 , dy2 in detected_boxes:
                inter_x1 = max(tx1 , dx1)
                inter_y1 = max(ty1 , dy1)
                inter_x2 = min(tx2 , dx2)
                inter_y2 = min(ty2 , dy2)
                
                inter_area = max(0, inter_x2 - inter_x1) * max(0, inter_y2 - inter_y1)
                tracker_area = (tx2 - tx1) * (ty2 - ty1)

                overlap_ratio = inter_area / tracker_area if tracker_area > 0 else 0

                if overlap_ratio > 0.3:
                    matched = True
                    lost_target_count = 0
                    break

            if not matched:
                lost_target_count += 1
                
                if lost_target_count > max_lost_target:
                    tracking = False
                    tracker = None
                    box = None

        if not tracking and len(detected_boxes) > 0:
            best_box = min(
                detected_boxes,
                key=lambda b: abs(((b[0] + b[2]) // 2) - center_x)
            )

            x1, y1, x2, y2 = best_box
            box = best_box

            tracker = cv2.TrackerCSRT_create()
            tracker.init(frame, (x1, y1, x2 - x1, y2 - y1))
            tracking = True
            lost_target_count = 0
    
    if box is not None:
            x1, y1, x2, y2 = box
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

            cx = (x1 + x2) // 2
            cy = (y1 + y2) // 2
            cv2.circle(frame, (cx, cy), 5, (255, 0, 0), -1)

            error = ((w // 2) - cx)*10
            integral += error
            derivative = error - prev_error

            vx = 0.7 * prev_vx + 0.3 * max_speed
            omega = kp * error + ki * integral + kd * derivative
            omega = max(-max_speed, min(max_speed, omega))

            cv2.line(frame, (center_x, center_y), (cx, cy), (255, 255, 0), 2)
            cv2.putText(frame, f"err: {int(error)}",
                        ((center_x + cx) // 2, (center_y + cy) // 2),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)

            prev_error = error
            
    elif box is None:
            if lost_target_count > max_lost_target:
                    vx = 0.7 * prev_vx
                    omega = 100 if prev_error > 0 else -100

                    cv2.putText(
                        frame,
                        "SEARCH MODE",
                        (50, 100),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.8,
                        (0, 0, 255),
                        2
                    )

            elif lost_target_count > 0:
                    vx = last_cmd["linear"]
                    omega = last_cmd["angular"]

    vx = max(-max_speed, min(max_speed, vx))
    omega = max(-max_speed, min(max_speed, omega))

    if abs(vx) < 0.2:
        vx = 0
    if abs(omega) < 0.2:
        omega = 0

    send_twist(vx, omega)
    print("vx : ",vx , " omega: ",omega)

    prev_vx = vx
    last_cmd = {"linear": vx, "angular": omega}

    cv2.putText(frame, f"vx: {vx:.2f}", (w - 160, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

    cv2.putText(frame, f"omega: {omega:.2f}", (w - 160, 60),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

    stream_frame = frame.copy()
    

    cv2.imshow("Person Follower", frame)
    if cv2.waitKey(delay) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()