from setuptools import find_packages, setup

package_name = 'arcz_vision'

setup(
    name=package_name,
    version='0.0.1',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', ['launch/vision.launch.py']),
        ('share/' + package_name + '/config', ['config/zr10_mediamtx.yml']),
        ('share/' + package_name + '/web', [
            'web/index.html',
            'web/app.js',
            'web/reader.js',
            'web/styles.css',
            'web/LICENSE.mediamtx',
        ]),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Radek',
    maintainer_email='radek.domin@gmail.com',
    description='ZR-10 camera: WebRTC video gateway and gimbal control web UI',
    license='Apache-2.0',
    entry_points={
        'console_scripts': [
            'zr10_gateway = arcz_vision.zr10_bridge.gateway:main',
            'zr10_healthcheck = arcz_vision.zr10_bridge.healthcheck:main',
        ],
    },
)
