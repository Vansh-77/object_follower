#!/bin/bash

# =========================================
# Ultra Low Latency UDP Camera Stream
# Raspberry Pi Zero 2W -> Laptop
# =========================================

# Replace with your laptop IP
LAPTOP_IP="10.191.187.46"

# Stream settings
PORT=5000
WIDTH=640
HEIGHT=480
FPS=30
BITRATE=1000k

echo "========================================="
echo "Starting Ultra Low Latency UDP Stream..."
echo "Laptop IP : $LAPTOP_IP"
echo "Resolution: ${WIDTH}x${HEIGHT}"
echo "FPS       : $FPS"
echo "Port      : $PORT"
echo "========================================="

ffmpeg \
-fflags nobuffer \
-f v4l2 \
-input_format mjpeg \
-video_size ${WIDTH}x${HEIGHT} \
-framerate ${FPS} \
-i /dev/video0 \
-codec:v mpeg1video \
-b:v ${BITRATE} \
-r ${FPS} \
-f mpegts \
udp://${LAPTOP_IP}:${PORT}

