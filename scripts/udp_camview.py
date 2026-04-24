import cv2

cap = cv2.VideoCapture("udp://@:5000", cv2.CAP_FFMPEG)

while True:
    ret, frame = cap.read()

    if not ret:
        continue

    cv2.imshow("UDP Low Latency Stream", frame)

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()
