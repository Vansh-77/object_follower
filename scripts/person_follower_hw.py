import cv2
import socket
import json
from ultralytics import YOLO
import time

# ---------------- UDP SETUP ----------------
ESP_IP = "10.210.6.39"
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
kp = 0.01
ki = 0.0
kd = 0.0
prev_error = 0
integral = 0
max_speed = 10.0

# ---------------- State ----------------
lost_frames = 0
max_lost_frames = 10
prev_vx = 0
last_cmd = {"linear": 0.0, "angular": 0.0}
last_result = None
frame_count = 0

# ---------------- Camera ----------------
cap = cv2.VideoCapture(0 , cv2.CAP_V4L2)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
cap.set(cv2.CAP_PROP_FPS, 30)
cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

while True:
    cap.grab()
    cap.grab()
    ret, frame = cap.retrieve()

    if not ret or frame is None:
        continue

    # frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
    # frame = cv2.resize(frame, (320, 240))
    h, w = frame.shape[:2]

    # ✅ Cycles 0→1→2→0, never accumulates
    frame_count = (frame_count + 1) % 3
    if frame_count == 0:
        last_result = model(frame, imgsz=320, verbose=False , classes = [0])[0]

    result = last_result

    cv2.circle(frame, (w // 2, h // 2), 5, (0, 0, 255), -1)

    vx = 0.0
    omega = 0.0

    if result is not None and len(result.boxes) > 0:
        box = next((b for b in result.boxes if int(b.cls[0]) == 0), None)

        if box is not None:
            lost_frames = 0
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

            cx = (x1 + x2) // 2
            cy = (y1 + y2) // 2
            cv2.circle(frame, (cx, cy), 5, (255, 0, 0), -1)

            error = (w // 2) - cx
            integral += error
            derivative = error - prev_error

            vx = 0.7 * prev_vx + 0.3 * 10.0
            omega = kp * error + ki * integral + kd * derivative

            cv2.line(frame, (w // 2, h // 2), (cx, cy), (255, 255, 0), 2)
            cv2.putText(frame, f"err: {int(error)}",
                        ((w // 2 + cx) // 2, (h // 2 + cy) // 2),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
            prev_error = error
        else:
            lost_frames += 1
    else:
        lost_frames += 1

    if lost_frames > max_lost_frames:
        vx = 0.7 * prev_vx
        omega = 5 if prev_error > 0 else -5
    elif lost_frames > 0:
        vx = last_cmd["linear"]
        omega = last_cmd["angular"]

    vx = max(-max_speed, min(max_speed, vx))
    omega = max(-max_speed, min(max_speed, omega))
    if abs(vx) < 0.2: vx = 0
    if abs(omega) < 0.2: omega = 0

    send_twist(vx, omega)
    prev_vx = vx
    last_cmd = {"linear": vx, "angular": omega}

    cv2.putText(frame, f"vx: {vx:.2f}", (w - 160, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
    cv2.putText(frame, f"omega: {omega:.2f}", (w - 160, 60),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

    cv2.imshow("Person Follower", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
