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
lost_target_count = 0
max_lost_target = 2

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

 # ---------------- PERIODIC YOLO VALIDATION ----------------
    frame_count = (frame_count + 1) % (10 if tracking else 1) # every 10 frames

    if frame_count == 0:
        results = model(frame, imgsz=320, verbose=False, classes=[0])[0]

        detected_boxes = []

        for b in results.boxes:
            x1, y1, x2, y2 = map(int, b.xyxy[0])
            detected_boxes.append((x1, y1, x2, y2))

    # -------------------------------------------------
    # if already tracking → verify same person
    # -------------------------------------------------
        if tracking and box is not None:
            tx1, ty1, tx2, ty2 = box
            matched = False

            for dx1, dy1, dx2, dy2 in detected_boxes:
            # simple IOU-like overlap check
                inter_x1 = max(tx1, dx1)
                inter_y1 = max(ty1, dy1)
                inter_x2 = min(tx2, dx2)
                inter_y2 = min(ty2, dy2)

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
                    lost_target_count = 0

    # -------------------------------------------------
    # if not tracking → choose new target
    # -------------------------------------------------
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

    cv2.imshow("YOLO Person Tracking", frame)

    key = cv2.waitKey(delay) & 0xFF

    if key == ord("q"):
        break

    # press r to reset tracker manually
    if key == ord("r"):
        tracker = None
        tracking = False

cap.release()
cv2.destroyAllWindows()