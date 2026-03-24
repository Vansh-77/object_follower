from launch import LaunchDescription
from launch.actions import ExecuteProcess
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory
import os

def generate_launch_description():
    pkg_share = get_package_share_directory('object_follower')
    urdf_file = os.path.join(pkg_share, 'urdf', 'my_robot.urdf')
    world_file = os.path.join(pkg_share, 'world', 'object.sdf')

    # Read URDF
    with open(urdf_file, 'r') as infp:
        robot_desc = infp.read()

    return LaunchDescription([
        ExecuteProcess(
            cmd=['gz', 'sim', '-r','-v 4', world_file],
            output='screen'
        ),

        # Publish robot_state_publisher (so TF tree is available)
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            output='screen',
            parameters=[{'robot_description': robot_desc}]
        ),

        # Spawn robot into Gazebo
        Node(
            package='ros_gz_sim',
            executable='create',
            arguments=['-topic', 'robot_description', '-name', 'my_robot', '-z','0.05'],
            output='screen'
        ), 
        Node(
            package='ros_gz_bridge',
            executable='parameter_bridge',
            arguments=[
            '/cmd_vel@geometry_msgs/msg/Twist@gz.msgs.Twist',
            '/odom@nav_msgs/msg/Odometry@gz.msgs.Odometry',
            '/tf@tf2_msgs/msg/TFMessage@gz.msgs.Pose_V',
            '/joint_states@sensor_msgs/msg/JointState@gz.msgs.Model',
            '/camera/image@sensor_msgs/msg/Image@gz.msgs.Image'
            ],
            output='screen'
        ),
    ])
