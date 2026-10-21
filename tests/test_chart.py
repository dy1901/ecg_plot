import os
os.environ['MPLBACKEND'] = 'Agg'
import subprocess
import sys
import xml.etree.ElementTree as ET
import numpy as np
import pandas as pd
import pytest
import ecg_plot
from ecg_plot.chart import STANDARD_LEADS


def test_svg_without_optional_dependencies():
    code = '''
import sys
sys.modules['matplotlib'] = None
sys.modules['pandas'] = None
sys.modules['cairosvg'] = None
import ecg_plot
assert '<svg' in ecg_plot.plot([0, 1, 0], sample_rate=500).to_svg()
'''
    subprocess.run([sys.executable, '-c', code], check=True)


@pytest.mark.parametrize('n', [1, 7, 510, 1001, 4001])
def test_exact_samples(n):
    chart = ecg_plot.plot(np.zeros(n), sample_rate=500)
    assert len(chart.record.times) == n
    assert len(next(chart._wave_paths(chart.panels[0]))) == n
    ET.fromstring(chart.to_svg())


def test_dataframe_equivalence_units_and_snapshot():
    frame = pd.DataFrame({'I': [0., 1000., 0.], 'II': [0., 2000., 0.]})
    chart = ecg_plot.plot(frame, units='uV', sample_rate=100)
    other = ecg_plot.plot(frame.to_numpy().T/1000, lead_names=['I','II'], sample_rate=100)
    assert chart.to_svg() == other.to_svg()
    frame.iloc[0,0] = 99999
    assert chart.record.values[0,0] == 0
    assert ecg_plot.plot(frame['II']).record.names == ('II',)


def test_time_index():
    frame = pd.DataFrame({'II': [0,1,0]}, index=pd.to_timedelta([0,.01,.03], unit='s'))
    chart = ecg_plot.plot(frame)
    np.testing.assert_allclose(chart.record.times, [0,.01,.03])
    with pytest.raises(ValueError, match='conflicts'):
        ecg_plot.plot(frame, sample_rate=100)
    with pytest.raises(ValueError, match='strictly increasing'):
        ecg_plot.plot(frame.iloc[::-1])


def test_nan_breaks_and_xml_escaping():
    chart = ecg_plot.plot([0, 1, np.nan, 0, 1], title='A < B & C')
    paths = list(chart._wave_paths(chart.panels[0]))
    assert [len(p) for p in paths] == [2,2]
    root = ET.fromstring(chart.to_svg())
    assert root.find('{http://www.w3.org/2000/svg}title').text == 'A < B & C'


def test_physical_geometry_and_adapter():
    chart = ecg_plot.plot([0,1,0], sample_rate=1, speed=25, gain=10)
    panel = chart.panels[0]
    points = next(chart._wave_paths(panel))
    assert panel.width == 75
    assert points[1,0] - points[0,0] == 25
    assert points[0,1] - points[1,1] == 10
    fig, ax = chart.to_matplotlib()
    np.testing.assert_allclose(fig.get_size_inches()*25.4, [chart.width_mm,chart.height_mm])
    wave = [l for l in ax.lines if len(l.get_xdata()) == 3][-1]
    np.testing.assert_allclose(wave.get_xydata(), points)


def test_layouts_and_annotations():
    df = pd.DataFrame(np.zeros((1000,12)), columns=STANDARD_LEADS)
    chart = ecg_plot.plot(df, sample_rate=100, layout='12lead', time_mode='sequential', rhythm_lead='II')
    assert len(chart.panels) == 13
    assert [(chart.panels[i].start, chart.panels[i].end) for i in (0,3,6,9)] == [(0,2.5),(2.5,5),(5,7.5),(7.5,10)]
    assert chart.panels[-1].end == 10
    chart = ecg_plot.plot(df['II'], sample_rate=100, window=(2,4))
    chart.add_annotations([{'sample':250,'label':'R'}, {'time':1,'end_time':3,'label':'Noise'}], label='Reference')
    assert chart.annotations[0][0] == 2.5
    scenes = list(chart._scene())
    annotation_line = next(p for kind,_,p in scenes if kind=='line' and p['stroke']=='#00796b')
    assert annotation_line['x1'] == chart.panels[0].x + .5*25
    chart = ecg_plot.plot(np.zeros(2500), sample_rate=100, layout='rhythm', seconds_per_row=10)
    assert [p.end-p.start for p in chart.panels] == [10,10,5]


@pytest.mark.parametrize('data,kwargs', [([],{}), ([[1],[2,3]],{}), ([1,np.inf],{}), ([1,2],{'sample_rate':0}), ([1,2],{'units':'ADC'}), (np.zeros((2,3)),{'lead_names':['I','I']}), ([0,1],{'row_height':1})])
def test_invalid_input(data,kwargs):
    with pytest.raises(ValueError):
        ecg_plot.plot(data, **kwargs)


@pytest.mark.export
def test_repeated_export(tmp_path):
    from PIL import Image
    chart = ecg_plot.plot(np.sin(np.arange(100)/10), sample_rate=100)
    svg = chart.to_svg()
    ecg_plot.plot([3,2,1])  # another current chart must not affect chart.save
    for extension in ['svg','png','pdf','jpg']:
        path = chart.save(tmp_path/f'ecg.{extension}', dpi=150)
        assert path.stat().st_size > 100
    assert (tmp_path/'ecg.svg').read_text() == svg
    assert (tmp_path/'ecg.pdf').read_bytes().startswith(b'%PDF')
    with Image.open(tmp_path/'ecg.png') as im:
        assert im.width == round(chart.width_mm/25.4*150)
        assert im.height == round(chart.height_mm/25.4*150)
        assert abs(im.info['dpi'][0]-150) < .1
        assert np.asarray(im).std() > 0


def test_legacy_and_save_ownership(tmp_path):
    import matplotlib.pyplot as plt
    fig = ecg_plot.plot_12(np.zeros((2,1001)), line_width=2)
    waves = [line for line in fig.axes[0].lines if len(line.get_xdata()) == 1001]
    assert len(waves) == 2
    assert all(line.get_linewidth() == pytest.approx(2) for line in waves)
    ecg_plot.save_as_png('first', tmp_path)
    plt.figure()  # no longer redirects ECG saves to an empty figure
    ecg_plot.save_as_svg('second', tmp_path)
    assert 'path' in (tmp_path/'second.svg').read_text()
    assert ecg_plot.plot_12(np.zeros((1,500)), columns=1) is not None
    assert ecg_plot.plot_1(np.zeros(1001)) is not None
    with pytest.warns(DeprecationWarning):
        assert ecg_plot.plot(np.zeros((2,1001)), show_grid=False) is not None
    plt.close('all')


@pytest.mark.export
def test_publication_fit_updates_scale_and_pixels(tmp_path):
    from PIL import Image
    chart = ecg_plot.plot([0,1,0], sample_rate=1)
    width = chart.width_mm / 2
    root = ET.fromstring(chart.to_svg(width_mm=width))
    assert float(root.attrib['width'][:-2]) == width
    assert '12.5 mm/s' in chart.to_svg(width_mm=width)
    assert '5 mm/mV' in chart.to_svg(width_mm=width)
    assert '25 mm/s' in chart.to_svg()
    chart.save(tmp_path/'small.png', width_mm=width, dpi=100)
    with Image.open(tmp_path/'small.png') as image:
        assert image.width == round(width/25.4*100)
    fig, ax = chart.to_matplotlib(width_mm=width)
    assert fig.get_size_inches()[0]*25.4 == pytest.approx(width)


def test_panel_labels_have_vertical_clearance():
    chart = ecg_plot.plot(np.zeros((3,500)), layout='stacked')
    first, second = chart.panels[:2]
    time_label_baseline = first.y + first.height + 3.5
    lead_label_top = second.y - 1 - chart.style.font_size
    assert lead_label_top > time_label_baseline + 1


def test_legacy_long_record_uses_shared_time_labels():
    import matplotlib.pyplot as plt
    fig = ecg_plot.plot_1(np.zeros(10000))
    assert '20' in [text.get_text() for text in fig.axes[0].texts]
    with pytest.warns(DeprecationWarning):
        fig = ecg_plot.plot(np.array([np.full(500,i) for i in range(4)]), show_grid=False)
    # Shared viewports replace the old signal-dependent separator marks.
    assert len([line for line in fig.axes[0].lines if len(line.get_xdata()) == 500]) == 4
    assert not [line for line in fig.axes[0].lines if len(line.get_xdata()) == 2]
    assert 'OUT OF RANGE' in [text.get_text() for text in fig.axes[0].texts]
    plt.close('all')


def test_inline_svg_clip_ids_do_not_collide_between_layouts():
    a = ecg_plot.plot(np.zeros(500), sample_rate=500)
    b = ecg_plot.plot(np.zeros(1000), sample_rate=500)
    ns = {'s': 'http://www.w3.org/2000/svg'}
    ids_a = {e.attrib['id'] for e in ET.fromstring(a.to_svg()).findall('.//s:clipPath',ns)}
    ids_b = {e.attrib['id'] for e in ET.fromstring(b.to_svg()).findall('.//s:clipPath',ns)}
    assert ids_a.isdisjoint(ids_b)


def test_legacy_and_modern_share_geometry():
    import matplotlib.pyplot as plt
    data = np.vstack([np.linspace(-1,1,501), np.zeros(501)])
    old = ecg_plot.plot_12(data, speed=25, voltage=10, line_width=.72)
    chart = ecg_plot.plot(data, sample_rate=500, title='ECG 12',
                         lead_names=['I','II'], layout='row-major',
                         style=ecg_plot.Style(line_width=.72*25.4/72))
    modern, ax = chart.to_matplotlib()
    np.testing.assert_allclose(old.get_size_inches(), modern.get_size_inches())
    assert len(old.axes[0].lines) == len(ax.lines)
    for a,b in zip(old.axes[0].lines, ax.lines):
        np.testing.assert_allclose(a.get_xydata(), b.get_xydata())
        assert a.get_linewidth() == pytest.approx(b.get_linewidth())
    assert [t.get_text() for t in old.axes[0].texts] == [t.get_text() for t in ax.texts]
    assert plt.fignum_exists(old.number)
    plt.close('all')


def test_grouped_layout_is_name_based_and_row_major_is_compatible():
    names = list(reversed(STANDARD_LEADS))
    chart = ecg_plot.plot(np.zeros((12,500)), lead_names=names, layout='limb-chest')
    ordered = [chart.record.names[p.lead] for p in sorted(chart.panels,key=lambda p:(p.x,p.y))]
    assert ordered == list(STANDARD_LEADS)
    chart = ecg_plot.plot(np.zeros((12,500)), lead_names=STANDARD_LEADS, layout='row-major')
    ordered = [chart.record.names[p.lead] for p in sorted(chart.panels,key=lambda p:(p.y,p.x))]
    assert ordered == list(STANDARD_LEADS)


def test_calibration_and_tick_interval():
    chart = ecg_plot.plot(np.zeros(1000), sample_rate=100, speed=50, gain=20,
                         style=ecg_plot.Style(time_tick=2))
    pulse = next(props['points'] for kind,panel,props in chart._scene() if kind=='path' and panel is None)
    assert pulse[3,0]-pulse[2,0] == pytest.approx(10)  # .2 s x 50 mm/s
    assert pulse[1,1]-pulse[2,1] == pytest.approx(20)  # 1 mV x 20 mm/mV
    labels = [p['text'] for kind,_,p in chart._scene() if kind=='text']
    assert all(str(n) in labels for n in range(0,11,2))
    assert '1' not in labels


def test_annotation_lanes_preserve_markers_and_report_overflow():
    chart = ecg_plot.plot(np.zeros(1000), sample_rate=100)
    chart.add_annotations([{'time':1,'label':f'Event {i}'} for i in range(5)])
    scene = list(chart._scene())
    labels = [p for kind,_,p in scene if kind=='text' and p['text'].startswith('Event')]
    assert len(labels) == 3
    assert len({p['y'] for p in labels}) == 3
    assert any(kind=='text' and p['text']=='+2 labels' for kind,_,p in scene)
    assert len([p for kind,_,p in scene if kind=='line' and p['stroke']=='#00796b']) == 5


def test_explicit_amplitude_range_does_not_normalize():
    chart = ecg_plot.plot([0,20,0], sample_rate=1, amplitude_range=(-1,1))
    p = chart.panels[0]
    assert p.height == 20
    assert next(chart._wave_paths(p))[1,1] == p.baseline - 200
    assert 'OUT OF RANGE' in chart.to_svg()


def test_preview_keeps_extrema_endpoints_and_gaps():
    values = np.zeros(10000)
    values[333] = 7
    values[888] = -9
    values[5000] = np.nan
    chart = ecg_plot.plot(values, sample_rate=500)
    p = chart.panels[0]
    paths = list(chart._wave_paths(p, preview_points=100))
    assert len(paths) == 2
    assert all(len(a) <= 100 for a in paths)
    assert min(paths[0][:,1]) == p.baseline - 70
    assert max(paths[0][:,1]) == p.baseline + 90
    assert paths[0][0,0] == p.x
    assert paths[-1][-1,0] == p.x+9999/500*chart.speed
    assert 'PREVIEW' in chart.to_svg(preview_points=100)
    assert 'PREVIEW' not in chart.to_svg()
    assert sum(len(a) for a in chart._wave_paths(p)) == 9999
