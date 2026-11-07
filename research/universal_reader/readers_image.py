"""Raster images and GIMP XCF files.

Images are identified by their magic bytes, not their extension (computer.png is a JPEG in the snapshot).
The canonical node keeps metadata, a pixel hash, and channel statistics. Pixel arrays are decoded on
demand by load_pixels() and composite(), so the tree stays small and diffs stay fast.

XCF support covers file version v011 (the version in the snapshots): layer stack, names, offsets,
visibility, opacity, mode, the text-layer parasite, and a normal-mode composite. Pixel decoding covers RLE tiles
at 8-bit precision for RGB and RGBA layers only, and is gated by TILE_DECODE_VALIDATED. Other XCF versions,
compressions, precisions, layer types and blend modes raise XcfUnsupported.
In v011 every file pointer (layer, hierarchy, level, tile) is 64 bits wide, and the header has a precision
field after the base type; earlier versions use 32-bit pointers and no precision field.
"""
import functools
import hashlib
import re
import struct

import numpy as np
from PIL import Image

XCF_LAYER_TYPES = {0: 'RGB', 1: 'RGBA', 2: 'GRAY', 3: 'GRAYA', 4: 'INDEXED', 5: 'INDEXEDA'}
XCF_BASE_TYPES = {0: 'RGB', 1: 'GRAY', 2: 'INDEXED'}
TILE = 64
# Layer modes in v011 files: 0 is NORMAL_LEGACY and 28 is NORMAL (GIMP 2.10 enum values, checked against GIMP 2.10.36).
NORMAL_MODES = (0, 28)


class XcfUnsupported(Exception):
    pass


def _grid_mean(arr):
    h, w = arr.shape[:2]
    out = []
    for i in range(3):
        row = []
        for j in range(3):
            block = arr[i * h // 3:(i + 1) * h // 3, j * w // 3:(j + 1) * w // 3, :3]
            row.append([round(float(v), 2) for v in block.reshape(-1, 3).mean(axis=0)])
        out.append(row)
    return out


def read_raster(path):
    im = Image.open(path)
    im.load()
    palette = None
    if im.mode == 'P':
        pal = im.getpalette() or []
        n = max(2, min(256, len(pal) // 3))
        palette = [list(pal[3 * i:3 * i + 3]) for i in range(n)]
        arr = np.asarray(im.convert('RGB'))
    else:
        arr = np.asarray(im.convert('RGB'))
    mean = arr.reshape(-1, 3).mean(axis=0)
    node = {'format': im.format, 'mode': im.mode, 'width': im.width, 'height': im.height,
            'base_type': 'INDEXED' if im.mode == 'P' else ('GRAY' if im.mode in ('L', 'LA') else 'RGB'),
            'mean_rgb': {'R': round(float(mean[0]), 2), 'G': round(float(mean[1]), 2), 'B': round(float(mean[2]), 2)},
            'grid_mean_rgb': _grid_mean(arr), 'pixels_sha256': hashlib.sha256(np.ascontiguousarray(arr).tobytes()).hexdigest()}
    if palette is not None:
        node['colormap'] = palette
    return node


@functools.lru_cache(maxsize=32)
def load_pixels(path):
    """RGB array (H, W, 3) of a raster image, as uint8."""
    with Image.open(path) as im:
        return np.asarray(im.convert('RGB'))


# ---------------------------------------------------------------- XCF

PROP_END, PROP_COLORMAP, PROP_OPACITY, PROP_MODE, PROP_VISIBLE, PROP_OFFSETS = 0, 1, 6, 7, 8, 15
PROP_COMPRESSION, PROP_PARASITES = 17, 21


class _Reader:
    def __init__(self, data):
        self.d = data
        self.p = 0

    def u32(self):
        v = struct.unpack_from('>I', self.d, self.p)[0]
        self.p += 4
        return v

    def i32(self):
        v = struct.unpack_from('>i', self.d, self.p)[0]
        self.p += 4
        return v

    def offset(self):
        """A file pointer. XCF v011 stores pointers as 64-bit big-endian values."""
        v = struct.unpack_from('>Q', self.d, self.p)[0]
        self.p += 8
        return v

    def u8(self):
        v = self.d[self.p]
        self.p += 1
        return v

    def string(self):
        n = self.u32()
        raw = self.d[self.p:self.p + n]
        self.p += n
        return raw.rstrip(b'\0').decode('utf-8', 'replace')

    def props(self):
        out = {}
        while True:
            ptype = self.u32()
            size = self.u32()
            start = self.p
            if ptype == PROP_END:
                return out
            out[ptype] = (start, size)
            self.p = start + size


def _parse_props(data, pos):
    """Properties block at pos. Returns ({type: bytes}, end position)."""
    r = _Reader(data)
    r.p = pos
    raw = {}
    while True:
        ptype = r.u32()
        size = r.u32()
        if ptype == PROP_END:
            return raw, r.p
        raw[ptype] = data[r.p:r.p + size]
        r.p += size


def _parasites(blob):
    """Parasites inside PROP_PARASITES: name, flags, size, data (repeated)."""
    out = {}
    p = 0
    while p + 4 <= len(blob):
        n = struct.unpack_from('>I', blob, p)[0]
        name = blob[p + 4:p + 4 + n].rstrip(b'\0').decode('utf-8', 'replace')
        p += 4 + n
        _flags, size = struct.unpack_from('>II', blob, p)
        p += 8
        out[name] = blob[p:p + size]
        p += size
    return out


def _read_xcf_header(data):
    if not data.startswith(b'gimp xcf '):
        raise XcfUnsupported('not an XCF file')
    version = data[9:14]
    if version != b'v011\0':
        raise XcfUnsupported(f'XCF version {version!r} not supported (v011 only)')
    r = _Reader(data)
    r.p = 14
    width, height, base = r.u32(), r.u32(), r.u32()
    precision = r.u32()  # v011 adds it after the base type; 150 is 8-bit gamma
    props, r.p = _parse_props(data, r.p)
    compression = props[PROP_COMPRESSION][0] if PROP_COMPRESSION in props else 0
    colormap = None
    if PROP_COLORMAP in props:
        blob = props[PROP_COLORMAP]
        n = struct.unpack_from('>I', blob, 0)[0]
        colormap = [list(blob[4 + 3 * i:7 + 3 * i]) for i in range(n)]
    layer_ptrs = []
    while True:
        off = r.offset()
        if off == 0:
            break
        layer_ptrs.append(off)
    return {'width': width, 'height': height, 'base_type': XCF_BASE_TYPES.get(base, str(base)),
            'compression': compression, 'precision': precision, 'colormap': colormap, 'layer_ptrs': layer_ptrs}


def _read_layer(data, offset, compression):
    r = _Reader(data)
    r.p = offset
    w, h, ltype = r.u32(), r.u32(), r.u32()
    name = r.string()
    props, r.p = _parse_props(data, r.p)
    hier_off = r.offset()
    layer = {'name': name, 'width': w, 'height': h, 'type': XCF_LAYER_TYPES.get(ltype, str(ltype)),
             'visible': bool(struct.unpack('>I', props[PROP_VISIBLE])[0]) if PROP_VISIBLE in props else True,
             'opacity': struct.unpack('>I', props[PROP_OPACITY])[0] / 255 if PROP_OPACITY in props else 1.0,
             'mode': struct.unpack('>I', props[PROP_MODE])[0] if PROP_MODE in props else 0,
             'offset_x': 0, 'offset_y': 0, 'text': None, 'parasites': {}}
    if PROP_OFFSETS in props:
        layer['offset_x'], layer['offset_y'] = struct.unpack('>ii', props[PROP_OFFSETS])
    if PROP_PARASITES in props:
        pars = _parasites(props[PROP_PARASITES])
        layer['parasites'] = {k: len(v) for k, v in pars.items()}
        if 'gimp-text-layer' in pars:
            layer['text'] = _gimp_text_string(pars['gimp-text-layer'])
    layer['_hier'] = hier_off
    return layer


_GIMP_TEXT_FIELD = re.compile(r'\(text "((?:[^"\\]|\\.)*)"\)')
_SCHEME_ESCAPES = {'n': '\n', 't': '\t', 'r': '\r'}


def _gimp_text_string(blob):
    """The text of a GIMP text layer: the (text "...") field of its gimp-text-layer parasite.

    The parasite also holds font, size, colour and box settings, which are not the text. Scheme escapes in the
    string are decoded. None when the field is absent.
    """
    m = _GIMP_TEXT_FIELD.search(blob.decode('utf-8', 'replace'))
    if m is None:
        return None
    return re.sub(r'\\(.)', lambda e: _SCHEME_ESCAPES.get(e.group(1), e.group(1)), m.group(1))


def _rle_plane(data, pos, n):
    """One channel plane of an RLE tile, n bytes. Token t (checked against GIMP 2.10.36 output):
    t < 127: run of t + 1 copies of the next byte; t == 127: 16-bit big-endian count, then a value byte, run;
    t >= 128: literal of 256 - t bytes. A plane that does not end exactly at n bytes is an error."""
    out = bytearray()
    while len(out) < n:
        t = data[pos]
        pos += 1
        if t == 127:
            count = (data[pos] << 8) | data[pos + 1]
            out.extend(bytes([data[pos + 2]]) * count)
            pos += 3
        elif t < 127:
            out.extend(bytes([data[pos]]) * (t + 1))
            pos += 1
        else:
            count = 256 - t
            if pos + count > len(data):
                raise ValueError('literal runs past the end of the data')
            out.extend(data[pos:pos + count])
            pos += count
    if len(out) != n:
        raise ValueError('run overshoots the plane')
    return bytes(out), pos


def _decode_tiles(data, level_off, bpp):
    """RLE tiles of one level. Each tile stores its channels one after another; edge tiles are stored at their
    visible size (checked: the planes end exactly at the tile's size, see _rle_plane)."""
    r = _Reader(data)
    r.p = level_off
    lw, lh = r.u32(), r.u32()
    tile_offsets = []
    # The level's tile pointers follow the width and height, one per tile, in row-major order.
    ntx = (lw + TILE - 1) // TILE
    nty = (lh + TILE - 1) // TILE
    for _ in range(ntx * nty):
        tile_offsets.append(r.offset())
    planes = np.zeros((lh, lw, bpp), dtype=np.uint8)
    for idx, toff in enumerate(tile_offsets):
        ty, tx = divmod(idx, ntx)
        y0, x0 = ty * TILE, tx * TILE
        tw, th = min(TILE, lw - x0), min(TILE, lh - y0)
        pos = toff
        for c in range(bpp):
            plane, pos = _rle_plane(data, pos, tw * th)
            planes[y0:y0 + th, x0:x0 + tw, c] = np.frombuffer(plane, dtype=np.uint8).reshape(th, tw)
    return planes


TILE_DECODE_VALIDATED = True
"""Pixel reads (layers and composite) are enabled only because the decoder was checked against GIMP 2.10.36 output:
all 28 layers and all 14 composites of the 14 unique XCF files in the snapshots and end states match exactly
(see tests/data/xcf_gimp_reference.json). Setting this to False makes every XCF pixel UNSUPPORTED.
Validated scope: RLE compression, 8-bit gamma precision (150), RGB and RGBA layers, normal blend mode.
Anything outside that scope raises XcfUnsupported even when this flag is True."""
VALIDATED_PRECISION = 150
VALIDATED_COMPRESSION = 1
VALIDATED_LAYER_TYPES = ('RGB', 'RGBA')


def _layer_rgba(data, layer_info, head):
    """Decoded layer as RGBA (H, W, 4) uint8, positioned in its own rectangle (not on the canvas)."""
    if not TILE_DECODE_VALIDATED:
        raise XcfUnsupported('XCF tile decoding is not validated against GIMP output')
    colormap, compression = head['colormap'], head['compression']
    if head['precision'] != VALIDATED_PRECISION or compression != VALIDATED_COMPRESSION:
        raise XcfUnsupported(f"XCF precision {head['precision']} / compression {compression} not validated")
    ltype = layer_info['type']
    if ltype not in VALIDATED_LAYER_TYPES:
        raise XcfUnsupported(f'XCF layer type {ltype} not validated')
    bpp = {'RGB': 3, 'RGBA': 4}[ltype]
    r = _Reader(data)
    r.p = layer_info['_hier']
    _w, _h, _bpp = r.u32(), r.u32(), r.u32()
    level_ptrs = []
    while True:
        off = r.offset()
        if off == 0:
            break
        level_ptrs.append(off)
    try:
        planes = _decode_tiles(data, level_ptrs[0], bpp)
    except (IndexError, ValueError, struct.error) as e:
        # The tile stream does not decode with the rules implemented here. Pixels are then unreadable, not empty.
        raise XcfUnsupported(f"tile data of layer {layer_info['name']!r} does not decode: {type(e).__name__}")
    h, w = planes.shape[:2]
    if bpp == 4:
        return planes
    return np.concatenate([planes, np.full((h, w, 1), 255, np.uint8)], axis=2)


@functools.lru_cache(maxsize=16)
def _xcf_document(path, stamp):
    with open(path, 'rb') as f:
        data = f.read()
    head = _read_xcf_header(data)
    layers = [_read_layer(data, off, head['compression']) for off in head['layer_ptrs']]
    return data, head, layers


def read_xcf(path, stamp):
    """Canonical node for an XCF file. Layer metadata is always read. Pixel hashes are None when the tile data
    of a layer (or the composite) cannot be decoded, and the reason is kept in pixels_unreadable."""
    data, head, layers = _xcf_document(path, stamp)
    out_layers = {}
    for i, layer in enumerate(layers, 1):
        node = {k: v for k, v in layer.items() if not k.startswith('_')}
        node['pixel_source'] = {'layer_index': i}
        try:
            rgba = _layer_rgba(data, layer, head)
            node['pixels_sha256'] = hashlib.sha256(np.ascontiguousarray(rgba).tobytes()).hexdigest()
        except XcfUnsupported as e:
            node['pixels_sha256'] = None
            node['pixels_unreadable'] = str(e)
        out_layers[str(i)] = node
    try:
        comp = composite(path, stamp)
        comp_node = {'composite_sha256': hashlib.sha256(comp.tobytes()).hexdigest(),
                     'composite_mean_rgb': {'R': round(float(comp[..., 0].mean()), 2),
                                            'G': round(float(comp[..., 1].mean()), 2),
                                            'B': round(float(comp[..., 2].mean()), 2)}}
    except XcfUnsupported as e:
        comp_node = {'composite_sha256': None, 'composite_mean_rgb': None, 'composite_unreadable': str(e)}
    return dict({'format': 'xcf', 'version': 'v011', 'width': head['width'], 'height': head['height'],
                 'base_type': head['base_type'], 'compression': head['compression'], 'colormap': head['colormap'],
                 'layers': out_layers}, **comp_node)


def pixels_unreadable(content):
    """Reason string when a decoded XCF node has pixel data that could not be read, else None."""
    if not isinstance(content, dict) or content.get('format') != 'xcf':
        return None
    if content.get('composite_unreadable'):
        return content['composite_unreadable']
    for layer in (content.get('layers') or {}).values():
        if layer.get('pixels_unreadable'):
            return layer['pixels_unreadable']
    return None


def layer_pixels(path, stamp, index):
    """RGBA array of one layer, placed at its offset on a canvas the size of the image (transparent elsewhere)."""
    data, head, layers = _xcf_document(path, stamp)
    layer = layers[index - 1]
    rgba = _layer_rgba(data, layer, head)
    canvas = np.zeros((head['height'], head['width'], 4), dtype=np.uint8)
    ox, oy = layer['offset_x'], layer['offset_y']
    h, w = rgba.shape[:2]
    x0, y0 = max(0, ox), max(0, oy)
    x1, y1 = min(head['width'], ox + w), min(head['height'], oy + h)
    if x1 > x0 and y1 > y0:
        canvas[y0:y1, x0:x1] = rgba[y0 - oy:y1 - oy, x0 - ox:x1 - ox]
    return canvas


def _srgb_to_linear(v):
    return np.where(v <= 0.04045, v / 12.92, ((v + 0.055) / 1.055) ** 2.4)


def _linear_to_srgb(lin):
    lin = np.clip(lin, 0.0, 1.0)
    return np.where(lin <= 0.0031308, lin * 12.92, 1.055 * np.power(lin, 1 / 2.4) - 0.055)


def composite(path, stamp):
    """Flattened RGB of the visible layers over white, normal mode, bottom layer first.

    GIMP 2.10.36 flattens these files in linear light: each layer's sRGB values are decoded, blended with its
    alpha times opacity, then encoded back to sRGB and rounded to the nearest 8-bit value. Checked pixel-exact
    against GIMP's flatten on all snapshot composites (see TILE_DECODE_VALIDATED)."""
    data, head, layers = _xcf_document(path, stamp)
    H, W = head['height'], head['width']
    out = np.ones((H, W, 3))
    for index in range(len(layers), 0, -1):
        layer = layers[index - 1]
        if not layer['visible']:
            continue
        if layer['mode'] not in NORMAL_MODES:
            raise XcfUnsupported(f"blend mode {layer['mode']} not supported")
        src = layer_pixels(path, stamp, index).astype(np.float64)
        alpha = src[..., 3:4] / 255.0 * layer['opacity']
        out = _srgb_to_linear(src[..., :3] / 255.0) * alpha + out * (1 - alpha)
    return np.round(_linear_to_srgb(out) * 255).astype(np.uint8)


def read_image(path, stamp, kind):
    if kind == 'xcf':
        return read_xcf(path, stamp)
    return read_raster(path)
