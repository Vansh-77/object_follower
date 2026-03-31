#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from geometry_msgs.msg import Twist
from cv_bridge import CvBridge
import cv2
import numpy as np
from ultralytics import YOLO

class PersonFollower(Node):

    def __init__(self):
        super().__init__('person_follower')
        
        self.last_twist = Twist()
        self.prev_error = 0
        self.integral = 0
        self.kp = 0.006
        self.ki = 0.0
        self.kd = 0.001
        self.lost_frames = 0
        self.max_lost_frames = 10
        self.prev_xvel = 0
        

        self.sub = self.create_subscription(
            Image,
            '/camera/image',
            self.image_callback,
            10)

        self.pub = self.create_publisher(Twist, '/cmd_vel', 10)

        self.bridge = CvBridge()
        self.model =  YOLO("yolov8n.pt")

    def image_callback(self, msg):

        frame = self.bridge.imgmsg_to_cv2(msg, 'bgr8')
        h, w, _ = frame.shape
        result = self.model(frame)[0]
        twist = Twist()
        
        if len(result.boxes) > 0:
            self.lost_frames = 0
            box = result.boxes[0]
            x1 , y1 , x2 , y2  = map(int , box.xyxy[0])
            cv2.rectangle(frame , (x1,y1) , (x2 , y2) , (0,255,0) ,2)
            cx = (x1 + x2)//2
            cv2.circle(frame , (cx , (y1+y2)//2) , 5 , (255,0,0), -1)
            error = (w/2) - cx
            self.integral += error 
            area = (x2 - x1) * (y2 - y1)

            if area > 10000:
                twist.linear.x = (0.7 * self.prev_xvel )
                twist.angular.z = (
                    self.kp * error +
                    self.ki * self.integral +
                    self.kd * (error - self.prev_error)
                )      
                self.prev_error = error
                self.last_twist = twist
            else:
                twist.linear.x = (0.7 * self.prev_xvel + 0.3 * 1.0 )  
                twist.angular.z = (
                    self.kp * error +
                    self.ki * self.integral +
                    self.kd * (error - self.prev_error)
                )      
                self.prev_error = error
                self.last_twist = twist
        else:
            self.lost_frames += 1
            if self.lost_frames > self.max_lost_frames:
                twist.linear.x = (0.7 * self.prev_xvel )
                twist.angular.z = 1.0 if self.prev_error > 0 else -1.0
            else :
                twist = self.last_twist
        self.prev_xvel = twist.linear.x      
        self.pub.publish(twist)
        cv2.imshow('object follower' , frame)
        cv2.waitKey(1)
                             
            
def main(args=None):
	rclpy.init(args=args)
	node = PersonFollower()
	rclpy.spin(node)
	rclpy.shutdown()
if __name__ == '__main__':
	main()
