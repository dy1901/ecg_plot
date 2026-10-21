"""ECG plotting with SVG-first output and optional Matplotlib compatibility."""
from .api import (plot, plot_1, plot_12, show, show_svg,
                  save_as_png, save_as_svg, save_as_jpg, save_as_pdf)
from .chart import ECGChart, Style

__version__ = '0.3.0'
__all__ = ['plot', 'ECGChart', 'Style', 'plot_1', 'plot_12', 'show', 'show_svg',
           'save_as_png', 'save_as_svg', 'save_as_jpg', 'save_as_pdf']
