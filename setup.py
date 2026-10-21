from pathlib import Path
import re
from setuptools import setup

# PyPI does not resolve repository-relative README links. Keep the repository
# README portable while giving the package description absolute asset URLs.
readme = Path(__file__).with_name('README.md').read_text(encoding='utf-8')
def published_link(match):
    image, label, target = match.groups()
    if '://' in target or target.startswith('#'):
        return match.group(0)
    base = ('https://raw.githubusercontent.com/dy1901/ecg_plot/master/' if image
            else 'https://github.com/dy1901/ecg_plot/blob/master/')
    return f'{image}[{label}]({base}{target})'

long_description = re.sub(r'(!?)\[([^\]]*)\]\(([^)]+)\)', published_link, readme)

setup(
    name='ecg_plot',
    version='0.3.0',
    author='dy1901',
    author_email='dy1901@gmail.com',
    license='MIT',
    description='SVG-first ECG charts with pandas and optional Matplotlib support',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/dy1901/ecg_plot',
    packages=['ecg_plot'],
    python_requires='>=3.10',
    install_requires=['numpy>=1.23'],
    extras_require={
        'pandas': ['pandas>=1.5'],
        'matplotlib': ['matplotlib>=3.6'],
        'export': ['CairoSVG>=2.7', 'Pillow>=9.2'],
        'test': ['pytest>=7', 'pandas>=1.5', 'matplotlib>=3.6', 'CairoSVG>=2.7', 'Pillow>=9.2'],
    },
    classifiers=['Programming Language :: Python :: 3',
                 'License :: OSI Approved :: MIT License',
                 'Operating System :: OS Independent'],
)
