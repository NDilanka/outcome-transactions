"""Raster images and GIMP XCF files.

Images are identified by their magic bytes, not their extension (computer.png is a JPEG in the snapshot).
The canonical node keeps metadata, a pixel hash, and channel statistics. Pixel arrays are decoded on
demand by load_pixels() and composite(), so the tree stays small and diffs stay fast.

XCF support covers file version v011 (the version in the snapshots): layer stack, names, offsets,
visibility, opacity, mode, the text-layer parasite, tile decoding (none and RLE compression), and a
normal-mode composite. Other XCF versions and blend modes raise XcfUnsupported.
In v011 every file pointer (layer, hierarchy, level, tile) is 64 bits wide, and the header has a precision
field after the base type; earlier versions use 32-bit pointers and no precision field.
"""
import functools
import hashlib
import struct

import numpy as np
from PIL import Image

XCF_LAYER_TYPES = {0: 'RGB', 1: 'RGBA', 2: 'GRAY', 3: 'GRAYA', 4: 'INDEXED', 5: 'INDEXEDA'}
XCF_BASE_TYPES = {0: 'RGB', 1: 'GRAY', 2: 'INDEXED'}
TILE = 64


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
    r.u32()  # precision (v011 adds it after the base type; 150 is 8-bit gamma). Not used.
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
            'compression': compression, 'colormap': colormap, 'layer_ptrs': layer_ptrs}


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
            layer['text'] = pars['gimp-text-layer'].decode('utf-8', 'replace')
    layer['_hier'] = hier_off
    return layer


def _rle_plane(data, pos, n):
    out = bytearray()
    while len(out) < n:
        v = data[pos]
        pos += 1
        if v >= 128:
            count = 256 - v
            out.extend(bytes([data[pos]]) * count)
            pos += 1
        else:
            count = v + 1
            out.extend(data[pos:pos + count])
            pos += count
    return bytes(out[:n]), pos


def _decode_tiles(data, level_off, bpp, w, h, compression):
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
            if compression == 0:
                plane = data[pos:pos + tw * th]
                pos += tw * th
            elif compression == 1:
                plane, pos = _rle_plane(data, pos, tw * th)
            else:
                raise XcfUnsupported(f'XCF tile compression {compression} not supported')
            planes[y0:y0 + th, x0:x0 + tw, c] = np.frombuffer(plane, dtype=np.uint8).reshape(th, tw)
    return planes


TILE_DECODE_VALIDATED = False
"""Set to True only after the RLE tile decoder is checked against GIMP output. Until then, no XCF pixel is read:
an unvalidated decoder could return wrong pixels that compare as equal or unequal without warning."""


def _layer_rgba(data, layer_info, colormap, compression):
    """Decoded layer as RGBA (H, W, 4) uint8, positioned in its own rectangle (not on the canvas)."""
    if not TILE_DECODE_VALIDATED:
        raise XcfUnsupported('XCF tile decoding is not validated against GIMP output')
    ltype = layer_info['type']
    bpp = {'RGB': 3, 'RGBA': 4, 'GRAY': 1, 'GRAYA': 2, 'INDEXED': 1, 'INDEXEDA': 2}[ltype]
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
        planes = _decode_tiles(data, level_ptrs[0], bpp, layer_info['width'], layer_info['height'], compression)
    except (IndexError, ValueError, struct.error) as e:
        # The tile stream does not decode with the rules implemented here. Pixels are then unreadable, not empty.
        raise XcfUnsupported(f"tile data of layer {layer_info['name']!r} does not decode: {type(e).__name__}")
    h, w = planes.shape[:2]
    if ltype in ('RGB', 'RGBA'):
        rgba = planes if bpp == 4 else np.concatenate([planes, np.full((h, w, 1), 255, np.uint8)], axis=2)
    elif ltype in ('GRAY', 'GRAYA'):
        g = planes[:, :, 0]
        a = planes[:, :, 1] if bpp == 2 else np.full((h, w), 255, np.uint8)
        rgba = np.stack([g, g, g, a], axis=2)
    else:
        if colormap is None:
            raise XcfUnsupported('indexed layer without colormap')
        pal = np.array(colormap, dtype=np.uint8)
        idx = planes[:, :, 0]
        rgb = pal[np.minimum(idx, len(pal) - 1)]
        a = planes[:, :, 1] if bpp == 2 else np.full((h, w), 255, np.uint8)
        rgba = np.concatenate([rgb, a[:, :, None]], axis=2)
    return rgba


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
            rgba = _layer_rgba(data, layer, head['colormap'], head['compression'])
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
    rgba = _layer_rgba(data, layer, head['colormap'], head['compression'])
    canvas = np.zeros((head['height'], head['width'], 4), dtype=np.uint8)
    ox, oy = layer['offset_x'], layer['offset_y']
    h, w = rgba.shape[:2]
    x0, y0 = max(0, ox), max(0, oy)
    x1, y1 = min(head['width'], ox + w), min(head['height'], oy + h)
    if x1 > x0 and y1 > y0:
        canvas[y0:y1, x0:x1] = rgba[y0 - oy:y1 - oy, x0 - ox:x1 - ox]
    return canvas


def composite(path, stamp):
    """Flattened RGB of the visible layers, normal mode, over white. Bottom layer first."""
    data, head, layers = _xcf_document(path, stamp)
    H, W = head['height'], head['width']
    out = np.full((H, W, 3), 255.0)
    for index in range(len(layers), 0, -1):
        layer = layers[index - 1]
        if not layer['visible']:
            continue
        if layer['mode'] != 0:
            raise XcfUnsupported(f"blend mode {layer['mode']} not supported")
        src = layer_pixels(path, stamp, index).astype(np.float64)
        alpha = src[..., 3:4] / 255.0 * layer['opacity']
        out = src[..., :3] * alpha + out * (1 - alpha)
    return np.clip(np.round(out), 0, 255).astype(np.uint8)


def read_image(path, stamp, kind):
    if kind == 'xcf':
        return read_xcf(path, stamp)
    return read_raster(path)
