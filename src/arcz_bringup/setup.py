from setuptools import find_packages, setup

package_name = 'arcz_bringup'

setup(
    name=package_name,
    version='0.0.1',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', ['launch/bringup.launch.py']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Radek',
    maintainer_email='radek.domin@gmail.com',
    description='Top-level launch/config that brings up the whole arcz stack',
    license='Apache-2.0',
    entry_points={
        'console_scripts': [],
    },
)
