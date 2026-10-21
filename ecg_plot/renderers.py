"""Backend adapters for a generic scene in millimetres; no ECG layout logic."""
from dataclasses import dataclass
from typing import Iterable
import hashlib
import xml.etree.ElementTree as ET
import numpy as np

SVG = 'http://www.w3.org/2000/svg'
ET.register_namespace('', SVG)


@dataclass(frozen=True)
class Scene:
    width_mm: float
    height_mm: float
    title: str
    clips: tuple
    elements: Iterable
    scale: float = 1.


def render_svg(scene):
    scale = scene.scale
    root = ET.Element(f'{{{SVG}}}svg', width=f'{scene.width_mm * scale:g}mm', height=f'{scene.height_mm * scale:g}mm', viewBox=f'0 0 {scene.width_mm:g} {scene.height_mm:g}')
    ET.SubElement(root, f'{{{SVG}}}title').text = scene.title or 'ECG'
    # Inline SVGs in the same notebook share an ID namespace. Different
    # layouts need distinct clip IDs; identical geometry may safely share.
    prefix = hashlib.sha256(repr(scene.clips).encode()).hexdigest()[:16]
    defs = ET.SubElement(root, f'{{{SVG}}}defs')
    for i, (x, y, width, height) in enumerate(scene.clips):
        clip = ET.SubElement(defs, f'{{{SVG}}}clipPath', id=f'ecg-{prefix}-panel-{i}')
        ET.SubElement(clip, f'{{{SVG}}}rect', x=str(x), y=str(y), width=str(width), height=str(height))
    for kind, panel, props in scene.elements:
        props = props.copy()
        if kind == 'path':
            points = props.pop('points')
            props['d'] = 'M' + ' L'.join(f'{x:.6f},{y:.6f}' for x,y in points)
            props['fill'] = 'none'
            props['stroke-linecap'] = 'round'
            # Make isolated valid samples visible without bridging missing data.
            if len(points) == 1:
                props['d'] += f' L{points[0,0]:.6f},{points[0,1]:.6f}'
        if 'stroke' in props:
            props['stroke-width'] = props.pop('width')
        text = props.pop('text', None)
        if kind == 'text':
            props['font-size'] = props.pop('size')
            props['font-family'] = 'sans-serif'
            props['text-anchor'] = props.pop('anchor', 'start')
        if panel is not None:
            props['clip-path'] = f'url(#ecg-{prefix}-panel-{panel})'
        el = ET.SubElement(root, f'{{{SVG}}}{kind}', {k: str(v) for k,v in props.items()})
        if text is not None:
            el.text = text
    return ET.tostring(root, encoding='unicode')



def render_matplotlib(scene, *, figure=None):
    scale = scene.scale
    try:
        from matplotlib.figure import Figure
        from matplotlib.patches import Rectangle
    except ImportError as exc:
        raise ImportError('Install ecg_plot[matplotlib] for this adapter') from exc
    fig = figure if figure is not None else Figure(figsize=(scene.width_mm*scale/25.4, scene.height_mm*scale/25.4))
    ax = fig.add_axes([0,0,1,1])
    ax.set(xlim=(0,scene.width_mm), ylim=(scene.height_mm,0))
    ax.set_axis_off()
    clips = [Rectangle((x,y),w,h,transform=ax.transData) for x,y,w,h in scene.clips]
    for order, (kind, panel, props) in enumerate(scene.elements):
        p = props
        if kind == 'rect':
            artist = Rectangle((p['x'],p['y']),p['width'],p['height'],facecolor=p['fill'],edgecolor='none',alpha=p.get('opacity',1))
            ax.add_patch(artist)
        elif kind == 'text':
            artist = ax.text(p['x'],p['y'],p['text'],color=p['fill'],fontsize=p['size']*scale*72/25.4,va='baseline',ha={'start':'left','middle':'center','end':'right'}[p.get('anchor','start')])
        else:
            points = p['points'] if kind == 'path' else np.array([[p['x1'],p['y1']],[p['x2'],p['y2']]])
            artist, = ax.plot(points[:,0],points[:,1],color=p['stroke'],linewidth=p['width']*scale*72/25.4,solid_capstyle='round', marker='.' if len(points) == 1 else None, markersize=p['width']*scale*72/25.4)
        artist.set_zorder(order)
        if panel is not None:
            artist.set_clip_path(clips[panel])
            artist.set_clip_on(True)
    return fig, ax
