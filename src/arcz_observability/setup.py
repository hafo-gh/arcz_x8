from setuptools import find_packages, setup

package_name = 'arcz_observability'

setup(
    name=package_name,
    version='0.0.1',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', ['launch/observability.launch.py']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Radek',
    maintainer_email='radek.domin@gmail.com',
    description='Observability: MCAP recording of all topics while the vehicle is armed',
    license='Apache-2.0',
    entry_points={
        'console_scripts': [
            'mcap_recorder_node = arcz_observability.mcap_recorder_node:main',
        ],
    },
)
