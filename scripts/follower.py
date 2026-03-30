#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from geometry_msgs.msg import Twist
from cv_bridge import CvBridge
import cv2
import numpy as np

class ObjectFollower(Node):

    def __init__(self):
        super().__init__('object_follower')
        
        self.last_twist = Twist()
        self.prev_error = 0
        self.integral = 0
        self.kp = 0.01
        self.ki = 0.0001
        self.kd = 0.001
        

        self.sub = self.create_subscription(
            Image,
            '/camera/image',
            self.image_callback,
            10)

        self.pub = self.create_publisher(Twist, '/cmd_vel', 10)

        self.bridge = CvBridge()

    def image_callback(self, msg):

        frame = self.bridge.imgmsg_to_cv2(msg, 'bgr8')
        h, w, _ = frame.shape

        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        # orange cone mask
        lower = np.array([0, 50, 50])
        upper = np.array([30, 255, 255])

        mask = cv2.inRange(hsv, lower, upper)

        contours, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

        twist = Twist()

        if contours:

            c = max(contours, key=cv2.contourArea)
            x, y, wc, hc = cv2.boundingRect(c)
            cv2.rectangle(frame, (x,y), (x+wc, y+hc), (0,255,0), 2)
            cv2.circle(frame , (x + wc//2, y+ hc//2), 5, (255,0,0) , -1)   
        
            cx = x + wc//2

            error = (w/2) - cx
            self.integral += error
            if cv2.contourArea(c) > 5000:
               twist.linear.x = 0.0
               twist.angular.z = 0.0
               self.pub.publish(twist)
               self.destroy_node()
               rclpy.shutdown()
            else:
                twist.linear.x = 0.6
                twist.angular.z = (
                    self.kp * error + 
                    self.ki * self.integral + 
                    self.kd * (error -self.prev_error)
                )
            print("contour area:", cv2.contourArea(c))
            self.prev_error = error
            self.last_twist = twist
        else:
            twist.linear.x = 0.0
            twist.angular.z = 1.0
        self.pub.publish(twist)
        cv2.imshow('object follower' , frame)
        cv2.imshow('mask' , mask)
        cv2.waitKey(1)


def main(args=None):
	rclpy.init(args=args)
	node = ObjectFollower()
	rclpy.spin(node)
	rclpy.shutdown()
if __name__ == '__main__':
	main()
