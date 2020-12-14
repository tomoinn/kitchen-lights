
__author__ = 'tom'
from setuptools import setup, find_namespace_packages

# To build for local development use 'python setup.py develop'.
# To upload a version to pypi use 'python setup.py clean sdist upload'.
# Docs are built with 'make html' in the docs directory parallel to this one
setup(
    name='lights',
    version='0.1',
    description='Kitchen LED control',
    classifiers=['Programming Language :: Python :: 3.8'],
    url='https://github.com/tomoinn/kitchen-lights',
    author='Tom Oinn',
    author_email='tomoinn@gmail.com',
    license='ASL2.0',
    packages=find_namespace_packages(),
    install_requires=['gevent', 'flask', 'adafruit-blinka', 'adafruit-circuitpython-neopixel', 'paho-mqtt'],
    include_package_data=True,
    test_suite='nose.collector',
    tests_require=['nose'],
    dependency_links=[],
    zip_safe=False)