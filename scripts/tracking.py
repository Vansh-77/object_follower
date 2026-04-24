import cv2
from ultralytics import YOLO

# ---------------- YOLO ----------------
model = YOLO("yolov8n.pt")

# ---------------- Camera ----------------
cap = cv2.VideoCapture("../sample_videos/people-detection.mp4")
fps = cap.get(cv2.CAP_PROP_FPS)
delay = int(1000 / fps)

# ---------------- Tracker ----------------
tracker = None
tracking = False

frame_count = 0
results = None

while True:
    ret, frame = cap.read()
    if not ret:
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        continue

    h, w = frame.shape[:2]
    center_x = w // 2
    center_y = h // 2

    # frame center
    cv2.circle(frame, (center_x, center_y), 5, (0, 0, 255), -1)

    box = None

    # ---------------- TRACKER FIRST ----------------
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

    # ---------------- YOLO DETECTION ----------------
    frame_count = (frame_count + 1)%2
    if (not tracking and (frame_count == 0)):
        results = model(frame, imgsz=320, verbose=False, classes=[0])[0]

        if results is not None and len(results.boxes) > 0:
            # choose person nearest to center
            best_box = min(
                results.boxes,
                key=lambda b: abs(
                    ((int(b.xyxy[0][0]) + int(b.xyxy[0][2])) // 2) - center_x
                )
            )

            x1, y1, x2, y2 = map(int, best_box.xyxy[0])
            box = (x1, y1, x2, y2)

            # initialize tracker
            tracker = cv2.TrackerCSRT_create()
            tracker.init(frame, (x1, y1, x2 - x1, y2 - y1))
            tracking = True

            cv2.putText(
                frame,
                "YOLO LOCK",
                (x1, y1 - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2
            )

    # ---------------- DRAW ----------------
    if box is not None:
        x1, y1, x2, y2 = box

        # bounding box
        cv2.rectangle(
            frame,
            (x1, y1),
            (x2, y2),
            (0, 255, 0),
            2
        )

        # center point
        cx = (x1 + x2) // 2
        cy = (y1 + y2) // 2

        cv2.circle(
            frame,
            (cx, cy),
            5,
            (255, 0, 0),
            -1
        )

        # line to frame center
        cv2.line(
            frame,
            (center_x, center_y),
            (cx, cy),
            (255, 255, 0),
            2
        )

        # error
        error = center_x - cx

        cv2.putText(
            frame,
            f"err: {error}",
            (50, 50),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 255),
            2
        )

    cv2.imshow("YOLO Hand/Person Tracking", frame)

    key = cv2.waitKey(delay) & 0xFF

    if key == ord("q"):
        break

    # press r to reset tracker manually
    if key == ord("r"):
        tracker = None
        tracking = False

cap.release()
cv2.destroyAllWindows()