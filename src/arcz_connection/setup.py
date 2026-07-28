from setuptools import find_packages, setup

package_name = 'arcz_connection'

setup(
    name=package_name,
    version='0.0.1',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', ['launch/connection.launch.py']),
        ('share/' + package_name + '/config', [
            'config/mavsplit.yaml',
            'config/mavlink_bridge.yaml',
            'config/mavlink_mappings.yaml',
        ]),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Radek',
    maintainer_email='radek.domin@gmail.com',
    description='Connectivity: mavlink split/bridge, zenoh router, foxglove bridge, internet connection',
    license='Apache-2.0',
    entry_points={
        'console_scripts': [
            'mavsplit_node = arcz_connection.mavsplit_node:main',
            'mavlink_bridge_node = arcz_connection.mavlink_bridge_node:main',
            'internet_connection_node = arcz_connection.internet_connection_node:main',
        ],
    },
)
