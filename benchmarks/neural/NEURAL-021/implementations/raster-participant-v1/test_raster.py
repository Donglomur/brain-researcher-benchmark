"""Generated image/content controls only; no authentic arrays, targets or processes.

Pillow imports/rendering occur only when this suite is explicitly run. No fixture
files are written; native PNG inspection/export is a separately bounded action.
"""
import ast
import hashlib
import json
from pathlib import Path
import struct
import sys
import types
import unittest
from unittest import mock
import zlib

HERE = Path(__file__).absolute().parent
IMPLEMENTATIONS = HERE.parent
sys.path.insert(0,str(HERE))
import raster as r


def load_delivery():
    path = IMPLEMENTATIONS/'paired-count-delivery-v1/delivery.py'
    source = path.read_bytes()
    if len(source) != 15991 or hashlib.sha256(source).hexdigest() != 'd900456bbe77c27d813a5d5d8dc8352e6c67071c83c15b9e33afe38076ce0da3':
        raise ValueError('exact original delivery source required')
    module = types.ModuleType('_n021_generated_raster_delivery')
    module.__file__ = str(path)
    sys.modules[module.__name__] = module
    exec(compile(source,str(path),'exec'),module.__dict__)
    return module


def pixels(rendered):
    return r._decode_png(rendered['png'],rendered['width'],rendered['height'])[0]


def region(body,width,x,y,w,h):
    return b''.join(body[(y+row)*width+x:(y+row)*width+x+w] for row in range(h))


def expected_text_patch(text,width):
    # Independent expected text/value selection; same explicitly pinned font.
    from PIL import Image, ImageDraw
    font,_ = r._font_bundle()
    image = Image.new('L',(width,22),255)
    try:
        ImageDraw.Draw(image).text((0,18),text,font=font,fill=17,anchor='ls',stroke_width=0)
        return image.tobytes()
    finally:
        image.close()


def make_png(width,height,scan,extra_chunk=None):
    header = struct.pack('>IIBBBBB',width,height,8,0,0,0,0)
    return (r.PNG_SIGNATURE+r._chunk(b'IHDR',header)+(extra_chunk or b'')+
            r._chunk(b'IDAT',zlib.compress(scan))+r._chunk(b'IEND',b''))


class RasterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.delivery = load_delivery()
        cls.counts = tuple(tuple(1000+100*b+u for u in range(65)) for b in range(35))
        cls.base_trial = cls.delivery.Trial('q0000','active',cls.counts,None)
        cls.svg = cls.delivery.render_svg(cls.base_trial)
        cls.base = r.render_svg(cls.svg)
        cls.base_pixels = pixels(cls.base)

    def trial(self,counts,training=None,condition='active'):
        return self.delivery.Trial('t0271' if training is not None else 'q0000',condition,counts,training)

    def test_complete_count_grid_corner_interior_and_final_cell_pixels(self):
        self.assertEqual((self.base['width'],self.base['height']),(1710,1710))
        # Every source cell has ink; selected independently valued landmarks
        # additionally match its expected glyph, catching transposition/index loss.
        for u in range(65):
            for b in range(35):
                patch = region(self.base_pixels,1710,92+b*46,230+u*22-18,46,22)
                self.assertLess(min(patch),255,(u,b))
        for b,u in [(0,0),(0,64),(34,0),(34,64),(17,32),(3,41)]:
            actual = region(self.base_pixels,1710,92+b*46,230+u*22-18,46,22)
            self.assertEqual(actual,expected_text_patch(str(1000+100*b+u),46))
        self.assertEqual(region(self.base_pixels,1710,92+34*46,184-18,46,22),
                         expected_text_patch('k34',46))
        self.assertEqual(region(self.base_pixels,1710,92+34*46,204-18,46,22),
                         expected_text_patch('+460',46))

    def test_same_width_digit_substitution_changes_only_expected_cell(self):
        changed = [list(row) for row in self.counts]
        changed[17][32] += 1
        output = r.render_svg(self.delivery.render_svg(self.trial(tuple(map(tuple,changed)))))
        new_pixels = pixels(output)
        differences = [i for i,(a,b) in enumerate(zip(self.base_pixels,new_pixels)) if a != b]
        self.assertTrue(differences)
        x,y = 92+17*46,230+32*22-18
        self.assertTrue(all(x <= i%1710 < x+46 and y <= i//1710 < y+22 for i in differences))
        self.assertNotEqual(output['pixels_sha256'],self.base['pixels_sha256'])
        self.assertNotEqual(output['svg_sha256'],self.base['svg_sha256'])

    def test_adjacent_int64_values_are_distinct_without_resizing_or_clipping(self):
        value = 2**63-1
        counts = tuple((value,)*65 for _ in range(35))
        a = r.render_svg(self.delivery.render_svg(self.trial(counts)))
        altered = [list(row) for row in counts];altered[34][64] -= 1
        b = r.render_svg(self.delivery.render_svg(self.trial(tuple(map(tuple,altered)))))
        self.assertEqual((a['width'],a['height'],b['width'],b['height']),(6365,1710,6365,1710))
        pa,pb = pixels(a),pixels(b)
        x,y = 92+34*179,230+64*22-18
        self.assertEqual(region(pa,6365,x,y,179,22),expected_text_patch(str(value),179))
        self.assertEqual(region(pb,6365,x,y,179,22),expected_text_patch(str(value-1),179))
        differing = [i for i,(x,y) in enumerate(zip(pa,pb)) if x != y]
        self.assertTrue(differing)
        self.assertTrue(all(x <= i%6365 < x+179 and y <= i//6365 < y+22 for i in differing))

    def test_typed_boundary_views_relayout_corresponding_cells_exactly(self):
        for viewport in ({'unit_start':60,'unit_stop':65,'bin_start':29,'bin_stop':35},
                         {'unit_start':64,'unit_stop':65,'bin_start':34,'bin_stop':35}):
            out = r.render_svg(self.delivery.render_svg(self.base_trial,**viewport))
            raw = pixels(out)
            self.assertEqual(out['width'],1300)
            self.assertEqual(out['height'],280+(viewport['unit_stop']-viewport['unit_start'])*22)
            for u in range(viewport['unit_start'],viewport['unit_stop']):
                for b in range(viewport['bin_start'],viewport['bin_stop']):
                    full = region(self.base_pixels,1710,92+b*46,230+u*22-18,46,22)
                    cropped = region(raw,out['width'],92+(b-viewport['bin_start'])*46,
                                     230+(u-viewport['unit_start'])*22-18,46,22)
                    self.assertEqual(full,cropped)

    def test_calibration_case_units_long_finite_labels_and_last_row_visible(self):
        values = tuple((-0.0,-1.234567890123456e-200) if j == 0 else
                       (5e-324,-1000000.0) if j == 29 else (j/13,-j/17) for j in range(30))
        trial = self.trial(self.counts,values,'passive')
        out = r.render_svg(self.delivery.render_svg(trial));raw = pixels(out)
        self.assertEqual((out['width'],out['height']),(1710,2420))
        for j in (0,29):
            label = f'{j:02d} | [{-100+20*j:+d},{-80+20*j:+d}) | {values[j][0]!r} | {values[j][1]!r}'
            self.assertEqual(region(raw,1710,20,1690+(j+1)*22-18,1200,22),
                             expected_text_patch(label,1200))
        self.assertEqual(region(raw,1710,20,1690-18,1200,22),expected_text_patch(r.TRAINING_HEADER,1200))
        header = r.HEADER_TEXT[2]
        actual = region(raw,1710,20,90-18,1200,22)
        self.assertEqual(actual,expected_text_patch(header,1200))
        self.assertNotEqual(actual,expected_text_patch(header.replace('m/s','M/S'),1200))
        self.assertEqual(out['profile']['font_size_px'],13)
        self.assertEqual(out['profile']['layout_engine'],'BASIC')

    def test_max_calibration_geometry_and_declared_png_bound(self):
        trial = self.trial(tuple((2**63-1,)*65 for _ in range(35)),tuple((1e-300,-0.0) for _ in range(30)))
        out = r.render_svg(self.delivery.render_svg(trial))
        self.assertEqual((out['width'],out['height']),(6365,2420))
        self.assertEqual(r.MAX_PIXELS,15403300)
        self.assertEqual(r.MAX_RAW,15405720)
        self.assertEqual(r.MAX_PNG,15406963)
        self.assertLessEqual(len(out['png']),r.MAX_PNG)
        self.assertEqual(r.validate_png(out['png'],6365,2420)['pixels_sha256'],out['pixels_sha256'])

    def test_original_axes_case_order_count_and_label_edits_are_refused(self):
        mutations = [self.svg.replace('velocity x/y in m/s','velocity x/y in M/S'),
            self.svg.replace('k34</text>','k33</text>'),
            self.svg.replace('data-unit="64" data-bin="34"','data-unit="63" data-bin="34"'),
            self.svg.replace('>4464</text>','>9223372036854775808</text>'),
            self.svg.replace('>4464</text>','>-1</text>'),
            self.svg.replace('width="1710" height="1710" viewBox="0 0 1710 1710"',
                             'width="1300" height="1710" viewBox="0 0 1300 1710"')]
        for source in mutations:
            with self.subTest(source=source[:100]),self.assertRaises(ValueError):
                r.parse_svg(source)
        training = self.delivery.render_svg(self.trial(self.counts,tuple((0.,0.) for _ in range(30))))
        with self.assertRaises(ValueError):
            r.parse_svg(training.replace('29 | [+480,+500)','29 | [+480,+520)'))
        with self.assertRaises(ValueError):
            r.parse_svg(self.delivery.render_svg(self.trial(self.counts,tuple((0.,0.) for _ in range(30))),
                                                unit_start=0,unit_stop=1,bin_start=0,bin_stop=1))

    def test_xml_active_content_hidden_text_and_auxiliary_attributes_refused(self):
        well_formed = [
            self.svg.replace('>q0000 | active | NEURAL-021</text>',
                             '>&#113;0000 | active | NEURAL-021</text>', 1),
            self.svg.replace('<svg xmlns="http://www.w3.org/2000/svg" ',
                             '<svg xmlns="http://www.w3.org/2000/svg" xmlns:ignored="urn:raw-table" ',1),
            self.svg.replace('<g ','<g xmlns:ignored="urn:raw-table" ',1),
            self.svg.replace('<g ','<g xmlns="http://www.w3.org/2000/svg" ',1),
            self.svg.replace('<text ','<text xmlns:ignored="urn:raw-table" ',1),
            self.svg.replace('>q0000 | active | NEURAL-021</text>',
                             '><tspan>q0000 | active | NEURAL-021</tspan></text>',1)]
        for source in well_formed:
            # These target the subset guard, not malformed-XML rejection.
            r.ET.fromstring(source)
        malicious = well_formed + ['<!DOCTYPE svg>'+self.svg,'<?xml version="1.0"?>'+self.svg,
            self.svg.replace('<rect','<!-- hidden --> <rect',1),
            self.svg.replace('<g ','<g transform="scale(0.5)" ',1),
            self.svg.replace('<g ','<g style="display:none" ',1),
            self.svg.replace('>q0000 | active','>hidden<tspan>q0000 | active',1),
            self.svg.replace('</g>','extra</g>',1),
            self.svg.replace('</svg>','<script>0</script></svg>',1),
            self.svg.replace('x="20" y="24"','x="20" y="24" onclick="0"',1),
            self.svg.replace('>q0000 | active','>q0000 | \u03b1ctive',1)]
        for source in malicious:
            with self.subTest(prefix=source[:80]),self.assertRaises(ValueError):
                r.parse_svg(source)

    def test_font_extent_hash_and_glyph_bounds_fail_closed_without_fallback(self):
        bad = mock.MagicMock()
        bad.__enter__.return_value.read.return_value = b'X'*r.FONT_BYTES
        info = types.SimpleNamespace(st_mode=0o100600,st_nlink=1,st_size=r.FONT_BYTES,
                                     st_dev=1,st_ino=1,st_mtime_ns=1,st_ctime_ns=1)
        with mock.patch.object(r.os,'open',return_value=987654321),\
                mock.patch.object(r.os,'fdopen',return_value=bad),\
                mock.patch.object(r.os,'fstat',return_value=info),\
                mock.patch.object(Path,'stat',return_value=info),self.assertRaisesRegex(ValueError,'unchanged bundled font'):
            r._font_bytes()
        font = mock.Mock();font.getbbox.return_value = (-100,-10,20,0)
        with mock.patch.object(r,'_font_bundle',return_value=(font,{})),self.assertRaisesRegex(ValueError,'ink fits'):
            r.render_svg(self.svg)

    def test_png_is_exact_metadata_free_grayscale_and_validates_pixels(self):
        meta = r.validate_png(self.base['png'],1710,1710)
        self.assertEqual(meta['chunks'],['IHDR','IDAT','IEND'])
        self.assertEqual(meta['mode'],'L')
        self.assertEqual(meta['pixels_sha256'],hashlib.sha256(self.base_pixels).hexdigest())
        self.assertEqual(meta['bytes'],len(self.base['png']))
        self.assertEqual(set(self.base),{'png','width','height','pixels_sha256','svg_sha256','profile'})
        self.assertNotIn('texts',self.base)
        with self.assertRaises(ValueError):r.validate_png(self.base['png'],1300,1710)
        with self.assertRaises(ValueError):r.validate_png(self.base['png'],True,1710)

    def test_png_text_exif_animation_extra_stream_and_trailing_bytes_refused(self):
        scan = b'\0\x11\xff\0\xff\x11'
        good = make_png(2,2,scan)
        bad = [good+b'x',good[:-1],good[:-4]+b'\0\0\0\0']
        for tag in (b'tEXt',b'iTXt',b'zTXt',b'eXIf',b'acTL'):
            bad.append(make_png(2,2,scan,r._chunk(tag,b'<svg>raw table</svg>')))
        header = struct.pack('>IIBBBBB',2,2,8,0,0,0,0)
        bad.append(r.PNG_SIGNATURE+r._chunk(b'IHDR',header)+r._chunk(b'IDAT',zlib.compress(scan)+zlib.compress(b'x'))+r._chunk(b'IEND',b''))
        for body in bad:
            with self.subTest(size=len(body)),self.assertRaises(ValueError):r.validate_png(body)

    def test_png_inflation_filter_and_dimensions_refused_before_unbounded_decode(self):
        for body in (make_png(2,2,b'\0\x11\xff\0\xff\x11x'),
                     make_png(2,2,b'\1\x11\xff\0\xff\x11'),
                     make_png(r.MAX_WIDTH+1,1,b'\0'),make_png(0,1,b'\0')):
            with self.assertRaises(ValueError):r.validate_png(body)
        with mock.patch.object(r.zlib,'decompressobj') as decoder,self.assertRaises(ValueError):
            r.validate_png(make_png(r.MAX_WIDTH+1,1,b'\0'))
        decoder.assert_not_called()

    def test_stored_deflate_bound_block_boundaries_and_encoder_fallback(self):
        for size in (0,1,65535,65536,131070):
            raw = b'A'*size
            encoded = r._stored_zlib(raw)
            self.assertEqual(len(encoded),size+5*max(1,(size+65534)//65535)+6)
            self.assertEqual(zlib.decompress(encoded),raw)
        raw_pixels = b'\x11\xff\xff\x11'
        with mock.patch.object(r.zlib,'compress',return_value=b'x'*100):
            encoded = r._encode_png(raw_pixels,2,2)
        self.assertEqual(r._decode_png(encoded)[0],raw_pixels)

    def test_deterministic_pixels_and_no_implicit_resize(self):
        again = r.render_svg(self.svg)
        self.assertEqual(again,self.base)
        self.assertEqual(again['profile']['resizing'],'none')
        self.assertEqual(again['profile']['font_sha256'],r.FONT_SHA256)
        with self.assertRaises(ValueError):
            r.parse_svg(self.svg.replace('viewBox="0 0 1710 1710"','viewBox="0 0 3420 3420"'))


if __name__ == '__main__':
    for option in list(sys.argv[1:]):
        if option.startswith('--implementations-root='):
            IMPLEMENTATIONS = Path(option.split('=',1)[1]);sys.argv.remove(option)
        elif option.startswith('--site-packages='):
            sys.path.insert(0,option.split('=',1)[1]);sys.argv.remove(option)
    unittest.main(verbosity=2)
