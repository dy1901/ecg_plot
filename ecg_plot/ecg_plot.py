"""Compatibility import path; all drawing is implemented by the shared core."""
from .api import (plot, plot_1, plot_12, show, show_svg,
                  save_as_png, save_as_svg, save_as_jpg, save_as_pdf)
from .chart import STANDARD_LEADS

lead_index = list(STANDARD_LEADS)
__all__ = ['plot', 'plot_1', 'plot_12', 'show', 'show_svg', 'save_as_png',
           'save_as_svg', 'save_as_jpg', 'save_as_pdf', 'lead_index']
