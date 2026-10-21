"""SVG-first ECG charts. All backends consume the same millimetre geometry."""
from dataclasses import dataclass
from pathlib import Path
import math
import tempfile
import webbrowser
import numpy as np
from .data import positive

from .renderers import Scene, render_svg, render_matplotlib
STANDARD_LEADS = ('I', 'II', 'III', 'aVR', 'aVL', 'aVF', 'V1', 'V2', 'V3', 'V4', 'V5', 'V6')


@dataclass(frozen=True)
class Style:
    grid: bool = True
    lead_names: bool = True
    axes: bool = True
    line_width: float = .18  # millimetres
    line_color: str = '#172331'
    major_color: str = '#e6b8b8'
    minor_color: str = '#f8ebeb'
    font_size: float = 3.0  # millimetres
    background: str = 'white'
    calibration: bool = True
    time_tick: float = 1.  # seconds, independent of grid spacing
    annotation_lanes: int = 3


@dataclass(frozen=True)
class Panel:
    lead: int
    start: float
    end: float
    x: float
    y: float
    width: float
    height: float
    baseline: float


class ECGChart:
    def __init__(self, record, *, title=None, layout='columns', columns=2,
                 speed=25, gain=10, window=None, rhythm_lead=None,
                 seconds_per_row=10, time_mode='simultaneous', style=None,
                 row_height=None, amplitude_range=None):
        self.record = record
        self.title = str(title) if title is not None else ''
        self.speed = positive(speed, 'speed')
        self.gain = positive(gain, 'gain')
        self.style = Style(line_color='black', major_color='#999999', minor_color='#dddddd') if style == 'bw' else (Style() if style is None else style)
        if not isinstance(self.style, Style):
            raise ValueError('style must be a Style object, "bw", or None')
        positive(self.style.line_width, 'line_width')
        positive(self.style.font_size, 'font_size')
        positive(self.style.time_tick, 'time_tick')
        if isinstance(self.style.annotation_lanes, bool) or not isinstance(self.style.annotation_lanes, (int, np.integer)) or self.style.annotation_lanes not in (1, 2, 3, 4):
            raise ValueError('annotation_lanes must be between 1 and 4')
        if layout not in ('stacked', 'columns', 'row-major', 'limb-chest', '12lead', 'rhythm'):
            raise ValueError('Unknown layout; use stacked, columns, row-major, limb-chest, 12lead or rhythm')
        if isinstance(columns, bool) or int(columns) != columns or columns < 1:
            raise ValueError('columns must be a positive integer')
        columns = int(columns)
        if time_mode not in ('simultaneous', 'sequential'):
            raise ValueError('time_mode must be simultaneous or sequential')
        if time_mode == 'sequential' and layout not in ('columns', 'row-major', '12lead'):
            raise ValueError('sequential time_mode requires columns or 12lead layout')
        if rhythm_lead is not None and layout != '12lead':
            raise ValueError('rhythm_lead requires layout="12lead"')
        times = record.times
        dt = 1 / record.sample_rate if record.sample_rate else (float(np.median(np.diff(times))) if len(times) > 1 else .002)
        duration = float(times[-1] + dt)
        if window is None:
            start, end = 0., duration
        else:
            try:
                start, end = map(float, window)
            except (TypeError, ValueError):
                raise ValueError('window must be (start_seconds, end_seconds)') from None
            if not np.isfinite([start, end]).all() or start < 0 or end <= start or end > duration + 1e-8:
                raise ValueError(f'window must lie within [0, {duration:g}] seconds')
        self.window = (start, end)
        self.annotations = []
        self.panels = []
        left, top, gap = max(12., self.speed * .2 + 7) if self.style.calibration else 12., (14. if self.title else 8.), 6.
        row_gap = max(10., self.style.font_size * 3 + 2)
        # Shared symmetric range avoids hidden amplitude rescaling across leads.
        visible = record.values[:, (times >= start) & (times < end)]
        finite = visible[np.isfinite(visible)]
        extent = max(1.5, float(np.max(np.abs(finite))) + .5) if finite.size else 1.5
        height = max(30., math.ceil(2 * extent * self.gain / 10) * 10)
        if row_height is not None:
            height = positive(row_height, 'row_height')
            if height < 2 * extent * self.gain:
                raise ValueError('row_height would clip the signal; increase it or omit it')
        self.amplitude_range = None
        if amplitude_range is not None:
            low, high = map(float, amplitude_range)
            if not np.isfinite([low, high]).all() or low >= high:
                raise ValueError('amplitude_range must be finite (low_mV, high_mV)')
            if row_height is not None:
                raise ValueError('Use amplitude_range or row_height, not both')
            self.amplitude_range = (low, high)
            height = (high - low) * self.gain
        baseline_offset = height / 2 if self.amplitude_range is None else self.amplitude_range[1] * self.gain
        def panel(lead, a, b, col, row):
            width = (b - a) * self.speed
            x = left + col * (width + gap)
            y = top + row * (height + row_gap)
            self.panels.append(Panel(lead, a, b, x, y, width, height, y + baseline_offset))
        n = len(record.names)
        if layout == 'rhythm':
            span = positive(seconds_per_row, 'seconds_per_row')
            row = 0
            for a in np.arange(start, end, span):
                for lead in range(n):
                    panel(lead, float(a), min(float(a + span), end), 0, row)
                    row += 1
        elif layout == 'limb-chest':
            if set(record.names) != set(STANDARD_LEADS):
                raise ValueError('limb-chest layout requires the twelve standard lead names')
            for index, name in enumerate(STANDARD_LEADS):
                col, row = divmod(index, 6)
                panel(record.names.index(name), start, end, col, row)
        elif layout == '12lead':
            if set(record.names) != set(STANDARD_LEADS):
                raise ValueError('12lead layout requires the twelve standard lead names')
            groups = [('I', 'II', 'III'), ('aVR', 'aVL', 'aVF'), ('V1', 'V2', 'V3'), ('V4', 'V5', 'V6')]
            span = (end - start) / 4 if time_mode == 'sequential' else end - start
            for col, group in enumerate(groups):
                a = start + col * span if time_mode == 'sequential' else start
                for row, name in enumerate(group):
                    panel(record.names.index(name), a, a + span, col, row)
            if rhythm_lead is not None:
                if rhythm_lead not in record.names:
                    raise ValueError('Unknown rhythm_lead')
                panel(record.names.index(rhythm_lead), start, end, 0, 3)
        else:
            cols = 1 if layout == 'stacked' else min(columns, n)
            rows = math.ceil(n / cols)
            span = (end - start) / cols if time_mode == 'sequential' else end - start
            for lead in range(n):
                col, row = (lead % cols, lead // cols) if layout == 'row-major' else divmod(lead, rows)
                a = start + col * span if time_mode == 'sequential' else start
                panel(lead, a, a + span, col, row)
        self.width_mm = max(80., self.style.font_size * 28, max(p.x + p.width for p in self.panels) + 8)
        self.height_mm = max(p.y + p.height for p in self.panels) + max(18., self.style.font_size * 5, self.gain + 4 if height < self.gain + 2 and self.style.calibration else 0)

    def add_annotations(self, annotations, *, label=None, color='#00796b'):
        """Add mappings/DataFrame rows in original record coordinates.

        Use time/end_time (seconds), or sample/end_sample (integer indices).
        lead may be omitted for global events. No interpolation or detection.
        """
        rows = annotations.to_dict('records') if hasattr(annotations, 'to_dict') else annotations
        pending = []
        for row in rows:
            def present(key):
                v = row.get(key)
                return v is not None and not (isinstance(v, (float, np.floating)) and np.isnan(v))
            if present('sample') == present('time'):
                raise ValueError('Each annotation needs exactly one of time or sample')
            def sample_time(key):
                v = row[key]
                if isinstance(v, bool) or int(v) != v or not 0 <= v < len(self.record.times):
                    raise ValueError(f'{key} must index the original record')
                return float(self.record.times[int(v)])
            if present('sample'):
                if present('end_time'):
                    raise ValueError('Use end_sample with sample annotations')
                start = sample_time('sample')
                end = sample_time('end_sample') if present('end_sample') else None
            else:
                if present('end_sample'):
                    raise ValueError('Use end_time with time annotations')
                start = float(row['time'])
                end = float(row['end_time']) if present('end_time') else None
            if not np.isfinite(start) or start < 0 or (end is not None and (not np.isfinite(end) or end <= start)):
                raise ValueError('Annotation times must be finite, nonnegative and ordered')
            lead = str(row['lead']) if present('lead') else None
            if lead is not None and lead not in self.record.names:
                raise ValueError(f'Unknown annotation lead: {lead}')
            text = str(row['label']) if present('label') else ''
            source = label or (str(row['source']) if present('source') else '')
            pending.append((start, end, lead, f'{source}: {text}' if source and text else source or text, color))
        self.annotations.extend(pending)
        return self

    def _wave_paths(self, p, preview_points=None):
        t = self.record.times
        # Include neighbouring samples, then clip to the viewport, retaining
        # the real line crossing a window boundary and NaN discontinuities.
        lo = max(0, int(np.searchsorted(t, p.start)) - 1)
        hi = min(len(t), int(np.searchsorted(t, p.end, side='right')) + 1)
        y = self.record.values[p.lead, lo:hi]
        x = p.x + (t[lo:hi] - p.start) * self.speed
        yy = p.baseline - y * self.gain
        valid = np.isfinite(yy)
        edges = np.diff(np.r_[False, valid, False].astype(int))
        for a, b in zip(np.where(edges == 1)[0], np.where(edges == -1)[0]):
            points = np.column_stack((x[a:b], yy[a:b]))
            if preview_points is not None and len(points) > preview_points:
                # Preserve first/last and both extrema per chronological bucket.
                # Process finite runs independently so NaN gaps remain gaps.
                edges = np.linspace(0, len(points), max(1, preview_points // 4) + 1, dtype=int)
                selected = []
                for left, right in zip(edges[:-1], edges[1:]):
                    chunk = points[left:right, 1]
                    selected.extend(sorted({left, right - 1, left + int(np.argmin(chunk)), left + int(np.argmax(chunk))}))
                points = points[selected]
            yield points

    def _scene(self, display_scale=1., preview_points=None):
        """Yield simple geometry in mm for both SVG and Matplotlib."""
        s = self.style
        if preview_points is not None and (isinstance(preview_points, bool) or int(preview_points) != preview_points or preview_points < 4):
            raise ValueError('preview_points must be an integer >= 4 per finite run')
        if preview_points is not None:
            preview_points = int(preview_points)
        yield ('rect', None, dict(x=0, y=0, width=self.width_mm, height=self.height_mm, fill=s.background))
        if self.title:
            yield ('text', None, dict(x=12, y=6, text=self.title, fill='black', size=s.font_size + 1))
        for i, p in enumerate(self.panels):
            if s.grid:
                for spacing, color, width in [(1., s.minor_color, .06), (5., s.major_color, .12)]:
                    for x in np.arange(0, p.width + 1e-7, spacing):
                        yield ('line', i, dict(x1=p.x+x, y1=p.y, x2=p.x+x, y2=p.y+p.height, stroke=color, width=width))
                    for dy in np.arange(math.ceil((p.y-p.baseline)/spacing)*spacing, p.y+p.height-p.baseline+1e-7, spacing):
                        yield ('line', i, dict(x1=p.x, y1=p.baseline+dy, x2=p.x+p.width, y2=p.baseline+dy, stroke=color, width=width))
            label_ends = [-math.inf] * s.annotation_lanes
            omitted = 0
            for start, end, lead, text, color in sorted(self.annotations, key=lambda a: a[0]):
                if lead is not None and lead != self.record.names[p.lead]:
                    continue
                if end is None:
                    if not p.start <= start < p.end:
                        continue
                    x = p.x + (start-p.start)*self.speed
                    yield ('line', i, dict(x1=x, y1=p.y, x2=x, y2=p.y+p.height, stroke=color, width=.2))
                else:
                    a, b = max(start, p.start), min(end, p.end)
                    if b <= a:
                        continue
                    x = p.x + (a-p.start)*self.speed
                    yield ('rect', i, dict(x=x, y=p.y, width=(b-a)*self.speed, height=p.height, fill=color, opacity=.15))
                # Estimate text bounds conservatively, using separate lanes.
                if text:
                    size = s.font_size * .8
                    text_width = sum(1. if ord(ch) > 127 else .65 for ch in text) * size
                    label_x = min(x + .5, p.x + p.width - text_width)
                    lane = next((j for j, end_x in enumerate(label_ends) if label_x >= max(p.x, end_x + 1)), None)
                    if lane is None:
                        omitted += 1
                    else:
                        label_ends[lane] = label_x + text_width
                        yield ('text', i, dict(x=label_x, y=p.y+(lane+1)*(size+1), text=text, fill=color, size=size))
            if omitted:
                yield ('text', None, dict(x=p.x+p.width, y=p.y-1, text=f'+{omitted} labels', fill='#8a3300', size=s.font_size*.7, anchor='end'))
            for points in self._wave_paths(p, preview_points):
                yield ('path', i, dict(points=points, stroke=s.line_color, width=s.line_width))
            if self.amplitude_range is not None:
                low, high = self.amplitude_range
                mask = (self.record.times >= p.start) & (self.record.times < p.end)
                values = self.record.values[p.lead, mask]
                if np.any((values < low) | (values > high)):
                    yield ('text', i, dict(x=p.x+1, y=p.y+p.height-1, text='OUT OF RANGE', fill='#a02020', size=s.font_size*.8))
            if s.calibration and p.x == min(q.x for q in self.panels) and (p.height >= self.gain + 2 or i == 0):
                right = p.x - 3
                left = right - .2 * self.speed
                bottom = p.y + max(p.height / 2 + self.gain / 2, self.gain + 2)
                pulse = np.array([[left-1,bottom],[left,bottom],[left,bottom-self.gain],
                                  [right,bottom-self.gain],[right,bottom],[right+1,bottom]])
                yield ('path', None, dict(points=pulse, stroke=s.line_color, width=s.line_width))
            if s.lead_names:
                yield ('text', None, dict(x=p.x, y=p.y-1, text=self.record.names[p.lead], fill='black', size=s.font_size))
            if s.axes:
                interval = s.time_tick * max(1, math.ceil((len(f'{p.end:g}')+2) * s.font_size * .6 / (self.speed*s.time_tick)))
                ticks = list(np.arange(math.ceil(p.start/interval)*interval, p.end+1e-9, interval))
                if not ticks or ticks[0] - p.start > interval*.4:
                    ticks.insert(0, p.start)
                for tick in ticks:
                    x = p.x + (tick-p.start)*self.speed
                    anchor = 'start' if tick == p.start else ('end' if abs(tick-p.end)<1e-7 else 'middle')
                    yield ('text', None, dict(x=x, y=p.y+p.height+3.5, text=f'{tick:g}', fill='#333333', size=s.font_size*.8, anchor=anchor))
        sections = [f'{self.speed * display_scale:g} mm/s', f'{self.gain * display_scale:g} mm/mV', 'time: s', 'amplitude: mV']
        if s.calibration:
            sections.append('calibration: 1 mV / 0.2 s')
        if preview_points:
            sections.append('PREVIEW')
        lines, current = [], ''
        size = s.font_size * .85
        for section in sections:
            candidate = current + ' · ' + section if current else section
            if len(candidate)*size*.6 > self.width_mm-20 and current:
                lines.append(current)
                current = section
            else:
                current = candidate
        lines.append(current)
        for j, text in enumerate(lines):
            yield ('text', None, dict(x=12, y=self.height_mm-3-(len(lines)-1-j)*(size+1), text=text, fill='black', size=size))


    def _render_scene(self, width_mm=None, preview_points=None):
        scale = 1. if width_mm is None else positive(width_mm, 'width_mm') / self.width_mm
        return Scene(self.width_mm, self.height_mm, self.title,
                     tuple((p.x, p.y, p.width, p.height) for p in self.panels),
                     self._scene(scale, preview_points=preview_points), scale)

    def to_svg(self, *, width_mm=None, preview_points=None):
        return render_svg(self._render_scene(width_mm, preview_points))

    def _repr_svg_(self):
        return self.to_svg()

    def save(self, path, *, dpi=300, width_mm=None):
        """Save without closing the chart or changing global plotting state."""
        path = Path(path)
        suffix = path.suffix.lower()
        if suffix not in ('.svg', '.png', '.pdf', '.jpg', '.jpeg'):
            raise ValueError('Supported formats: SVG, PNG, PDF, JPG')
        dpi = positive(dpi, 'dpi')
        scale = 1. if width_mm is None else positive(width_mm, 'width_mm') / self.width_mm
        svg = self.to_svg(width_mm=width_mm).encode('utf-8')
        if suffix == '.svg':
            path.write_bytes(svg)
            return path
        try:
            import cairosvg
        except (ImportError, OSError) as exc:
            raise ImportError('PNG/PDF export requires ecg_plot[export] and a working Cairo installation') from exc
        if suffix == '.pdf':
            cairosvg.svg2pdf(bytestring=svg, write_to=str(path))
        else:
            from io import BytesIO
            try:
                from PIL import Image
            except ImportError as exc:
                raise ImportError('Raster export requires ecg_plot[export]') from exc
            content = cairosvg.svg2png(bytestring=svg, output_width=max(1, round(self.width_mm*scale/25.4*dpi)), output_height=max(1, round(self.height_mm*scale/25.4*dpi)))
            with Image.open(BytesIO(content)) as image:
                if suffix in ('.jpg', '.jpeg'):
                    canvas = Image.new('RGB', image.size, 'white')
                    if image.mode == 'RGBA':
                        canvas.paste(image, mask=image.getchannel('A'))
                    else:
                        canvas.paste(image.convert('RGB'))
                    canvas.save(path, dpi=(dpi,dpi))
                else:
                    image.save(path, dpi=(dpi,dpi))
        return path

    def show(self):
        # Keep the file available for the browser after this function returns.
        with tempfile.NamedTemporaryFile(suffix='.svg', prefix='ecg-', delete=False) as f:
            f.write(self.to_svg().encode('utf-8'))
        path = Path(f.name)
        webbrowser.open(path.as_uri())
        return path

    def to_matplotlib(self, *, width_mm=None, preview_points=None):
        """Return an independent editable (Figure, Axes), coordinates in mm."""
        return render_matplotlib(self._render_scene(width_mm, preview_points))
