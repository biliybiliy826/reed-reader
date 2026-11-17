"""Reversible presentation of the site's already-rendered, authorized reading view.

No text extraction, canvas decoding, authentication access or hidden-content reveal.
"""

import json

# Only reader decoration/background is changed. Access/login/pay dialogs and the
# site's hidden source nodes keep their original display/visibility rules.
FISH_CSS = """
html.reed-fish, html.reed-fish body.wr_page_reader,
html.reed-fish #app, html.reed-fish #__nuxt,
html.reed-fish .readerContent, html.reed-fish .readerContent .app_content,
html.reed-fish .readerChapterContent {
    background: transparent !important;
    background-color: transparent !important;
    box-shadow: none !important;
    border-color: transparent !important;
}
html.reed-fish, html.reed-fish body.wr_page_reader {
    min-width: 0 !important; margin: 0 !important; padding: 0 !important;
    scrollbar-width: none !important;
}
html.reed-fish ::-webkit-scrollbar { width: 0 !important; height: 0 !important; }
html.reed-fish .readerTopBar, html.reed-fish .readerControls,
html.reed-fish .readerContentHeader, html.reed-fish .readerFooter,
html.reed-fish .readerContent .navBarOffset,
html.reed-fish .readerContent .chapterTitle {
    display: none !important;
}
html.reed-fish .readerContent .app_content {
    width: 100% !important; max-width: none !important; min-width: 0 !important;
    margin: 0 !important; padding: 8px 12px !important;
    box-sizing: border-box !important;
}
html.reed-fish .readerChapterContent {
    margin: 0 !important; padding: 0 !important; min-width: 0 !important;
    border: 0 !important;
}
html.reed-fish .wr_canvasContainer canvas {
    filter: var(--reed-ink-filter) !important;
    opacity: var(--reed-ink-opacity) !important;
}
"""


def presentation_script(enabled: bool, light_text: bool = False, text_opacity: int = 95) -> str:
    options = json.dumps({"enabled": enabled, "light": light_text,
                          "opacity": max(20, min(100, text_opacity)) / 100})
    css = json.dumps(FISH_CSS)
    return f"""(() => {{
        const opts = {options};
        const root = document.documentElement;
        const current = document.getElementById('reed-fish-style');
        const scroller = document.scrollingElement;
        const oldHeight = scroller ? scroller.scrollHeight - innerHeight : 0;
        const ratio = oldHeight > 0 ? scrollY / oldHeight : 0;
        if (!opts.enabled) {{
            current?.remove(); root.classList.remove('reed-fish');
            root.style.removeProperty('--reed-ink-filter');
            root.style.removeProperty('--reed-ink-opacity');
            return {{ok:true}};
        }}
        if (location.hostname !== 'weread.qq.com' || !location.pathname.startsWith('/web/reader/'))
            return {{ok:false, reason:'请先在微信读书打开一本书，再开启摸鱼模式。'}};
        if (!document.querySelector('.readerContent .readerChapterContent'))
            return {{ok:false, reason:'请先在官网右侧控件选择“上下滚动阅读”，再开启摸鱼模式。'}};
        const visibleCanvas = Array.from(document.querySelectorAll('.renderTargetContainer canvas'))
            .some(e => e.getBoundingClientRect().width > 0 && getComputedStyle(e).visibility !== 'hidden');
        if (!visibleCanvas)
            return {{ok:false, reason:'正文尚未显示，请先完成登录或加载正文，再开启摸鱼模式。'}};
        if (!current) {{
            const style = document.createElement('style');
            style.id = 'reed-fish-style'; style.textContent = {css};
            document.head.appendChild(style);
        }}
        root.style.setProperty('--reed-ink-filter', opts.light ? 'brightness(0) invert(1)' : 'brightness(0)');
        root.style.setProperty('--reed-ink-opacity', String(opts.opacity));
        root.classList.add('reed-fish');
        if (!current) {{
            // Width changes ask the official renderer to reflow its own canvas.
            // Preserve approximate chapter position without inspecting any text.
            dispatchEvent(new Event('resize'));
            setTimeout(() => {{
                if (root.classList.contains('reed-fish') && scroller)
                    scrollTo(0, ratio * Math.max(0, scroller.scrollHeight - innerHeight));
            }}, 350);
        }}
        return {{ok:true}};
    }})()"""


def scroll_script(direction: int) -> str:
    direction = 1 if direction > 0 else -1
    return f"""(() => {{
        const direction = {direction};
        const element = document.scrollingElement;
        if (!element) return false;
        if (direction > 0 && scrollY + innerHeight >= element.scrollHeight - 3) {{
            const next = Array.from(document.querySelectorAll('.readerFooter button'))
                .find(e => !e.disabled && /^(下一章|下一页)/.test(e.textContent.trim()));
            if (next) {{ next.click(); return true; }}
        }}
        scrollBy({{top:direction * Math.max(24, innerHeight * 0.75), behavior:'instant'}});
        return true;
    }})()"""
