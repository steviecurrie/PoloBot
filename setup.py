#from distutils.core import setup
from setuptools import setup

setup(
    name='PoloBot',
    version='0.0.1',
    packages=[''],
    url='',
    license='Do what thou wilt',
    author='Steven Currie',
    author_email='scayrsteven@gmail.com',
    description='Trading Bot to work on the Poloniex Exchange',
    requires=['pandas', 'numpy', 'poloniex']
)
