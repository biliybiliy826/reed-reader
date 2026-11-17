"""Small, original format fixtures generated in tests; no copyrighted books."""

import struct
from zipfile import ZIP_DEFLATED, ZipFile


def epub(path, bad_href=False):
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        archive.writestr("mimetype", "application/epub+zip")
        archive.writestr("META-INF/container.xml", '<container><rootfiles><rootfile full-path="OPS/content.opf"/></rootfiles></container>')
        archive.writestr("OPS/content.opf", '''<package xmlns="http://www.idpf.org/2007/opf">
        <metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>测试之书</dc:title><dc:creator>苇读</dc:creator></metadata>
        <manifest><item id="a" href="first.xhtml" media-type="application/xhtml+xml"/>
        <item id="b" href="second.xhtml" media-type="application/xhtml+xml"/></manifest>
        <spine><itemref idref="b"/><itemref idref="a"/></spine></package>'''.replace('first.xhtml', '../../escape.xhtml' if bad_href else 'first.xhtml'))
        archive.writestr("OPS/first.xhtml", '<html><head><title>禁止展示</title><script>alert(1)</script></head><body><h1>第一章</h1><p>正文甲😀</p></body></html>')
        archive.writestr("OPS/second.xhtml", '<html><body><h1>第二章</h1><p>正文乙</p></body></html>')
    return path


def mobi(path):
    """An uncompressed MOBI6 with a Palm database header and UTF-8 HTML record."""
    html = '<html><body><h1>第一章 微光</h1><p>这是原创的 MOBI 测试文本。</p></body></html>'.encode()
    title = b'Reed fixture'
    record = bytearray(0xE8)
    struct.pack_into('>HHIHHHH', record, 0, 1, 0, len(html), 1, 4096, 0, 0)
    record[16:20] = b'MOBI'
    struct.pack_into('>IIIII', record, 20, 0xD8, 2, 65001, 1, 6)
    for offset in (0x28, 0x2C, 0x50, 0x6C):
        struct.pack_into('>I', record, offset, 0xFFFFFFFF)
    struct.pack_into('>II', record, 0x54, len(record), len(title))
    record.extend(title)
    palm = bytearray(78)
    palm[:len(title)] = title
    palm[60:68] = b'BOOKMOBI'
    struct.pack_into('>H', palm, 76, 2)
    table = struct.pack('>IIII', 96, 0, 96 + len(record), 1)
    path.write_bytes(palm + table + b'\x00\x00' + record + html)
    return path
