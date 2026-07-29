from setuptools import find_packages, setup

package_name = 'arcz_postflight'

setup(
    name=package_name,
    version='0.0.1',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', ['launch/postflight.launch.py']),
        ('share/' + package_name + '/config', ['config/postflight_dump.yaml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Radek',
    maintainer_email='radek.domin@gmail.com',
    description='Post-flight data collection and resumable upload for the drone companion computer',
    license='Apache-2.0',
    entry_points={
        'console_scripts': [
            'collector_node = arcz_postflight.postflight_dump.collector_node:main',
            'uploader_node = arcz_postflight.postflight_dump.uploader_node:main',
            'queue_status_node = arcz_postflight.postflight_dump.queue_status_node:main',
        ],
    },
)
