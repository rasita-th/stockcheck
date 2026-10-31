"""Exercise the shipped product tours against a prepared Pages candidate."""
import argparse
from playwright.sync_api import sync_playwright

KEY = 'stockRadar.productGuide.v1'


def user_data(page):
    return page.evaluate("""() => Object.fromEntries(Object.keys(localStorage)
      .filter(key => /memo|portfolio|watchlist|screener/i.test(key))
      .map(key => [key, localStorage.getItem(key)]))""")


def in_viewport(page):
    page.wait_for_function("""() => {
      const r = document.querySelector('.guide-panel').getBoundingClientRect();
      return r.left >= 0 && r.top >= 0 && r.right <= innerWidth + 1 && r.bottom <= innerHeight + 1;
    }""")


def tour(page, base, name, count):
    path = 'market.html' if name == 'market' else 'index.html#' + name
    page.goto(base.rstrip('/') + '/' + path, wait_until='domcontentloaded')
    page.wait_for_function("""name => document.querySelector('.guide-menu')?.dataset.view === name""", arg=name)
    if name == 'today':
        page.wait_for_selector('#attentionPageP4 .p4-toolbar', state='visible')
    page.wait_for_function("document.querySelector('.guide-menu') && !document.querySelector('.guide-menu').hidden")
    assert page.locator('.guide-layer').is_hidden(), 'First visit must never force a modal'
    before = user_data(page)
    page.locator('.guide-menu [data-guide-action=start]').click()
    page.wait_for_selector('.guide-panel', state='visible')
    page.keyboard.press('Tab')
    assert page.evaluate("document.querySelector('.guide-panel').contains(document.activeElement)")
    for index in range(count):
        page.wait_for_function("""i => document.querySelector('.guide-top span').textContent.includes(`${i + 1} จาก`)""", arg=index)
        in_viewport(page)
        assert page.locator('.guide-spotlight').is_visible(), f'{name} step {index + 1} needs a real visible target'
        assert page.locator('.guide-spotlight').evaluate('node => getComputedStyle(node).animationName') == 'none'
        assert page.locator('.guide-figure').is_visible()
        assert 'ตัวอย่างประกอบ' in page.locator('.guide-figure').inner_text()
        if index == 1:
            page.locator('[data-guide-action=back]').click()
            page.wait_for_function("document.querySelector('.guide-top span').textContent.includes('1 จาก')")
            page.locator('[data-guide-action=next]').click()
        page.screenshot(path=f'/tmp/product-guide-{name}-{page.viewport_size["width"]}.png')
        page.locator('[data-guide-action=next]').click()
    assert page.locator('.guide-layer').is_hidden()
    saved = page.evaluate('key => JSON.parse(localStorage.getItem(key))', KEY)
    assert saved[name]['status'] == 'completed', saved
    assert before == user_data(page), 'Tours must not modify portfolio, screener or memo data'
    page.reload(wait_until='domcontentloaded')
    page.wait_for_function('name => document.querySelector(".guide-menu")?.dataset.view === name', arg=name)
    assert page.locator('.guide-menu').is_hidden(), 'Completed tour should not prompt again'
    page.locator('.guide-dock > [data-guide-action=menu]').click()
    page.locator('.guide-menu [data-guide-action=start]').click()
    page.keyboard.press('Escape')
    assert page.locator('.guide-layer').is_hidden()
    assert page.evaluate('document.activeElement?.dataset.guideAction') == 'menu'
    print(f'{name} width {page.viewport_size["width"]}: {count} steps, replay, keyboard, persistence and no user-data writes passed', flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-url', required=True)
    parser.add_argument('--chromium')
    args = parser.parse_args()
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=args.chromium, headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'])
        try:
            for width in (1440, 390):
                context = browser.new_context(viewport={'width': width, 'height': 900 if width > 767 else 740}, reduced_motion='reduce')
                page = context.new_page()
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                for name, count in [('scanner', 5), ('today', 4), ('memo', 4), ('market', 5)]:
                    tour(page, args.base_url, name, count)
                page.locator('.guide-dock > [data-guide-action=menu]').click()
                page.locator('.guide-menu [data-guide-topic=drawdown]').click()
                assert 'Drawdown' in page.locator('#product-guide-title').inner_text()
                in_viewport(page)
                page.keyboard.press('Escape')
                assert page.locator('.guide-layer').is_hidden()
                # Missing targets show an honest fallback rather than the wrong highlight.
                page.evaluate("document.querySelector('.fresh-card')?.remove(); document.querySelector('.intro')?.remove();")
                page.evaluate('window.StockRadarGuide.open()')
                assert page.locator('.guide-spotlight').is_hidden()
                assert 'ยังไม่แสดง' in page.locator('.guide-note').inner_text()
                page.keyboard.press('Escape')
                # Storage restrictions must not break the guide.
                page.evaluate('key => localStorage.removeItem(key)', KEY)
                page.reload(wait_until='domcontentloaded')
                page.wait_for_function('Boolean(window.StockRadarGuide)')
                page.evaluate("() => { Storage.prototype.setItem = () => { throw new Error('storage disabled'); }; }")
                page.evaluate('window.StockRadarGuide.open()')
                page.locator('[data-guide-action=skip]').click()
                assert page.locator('.guide-layer').is_hidden()
                assert not any('product-guide' in error for error in errors), errors
                context.close()
        finally:
            browser.close()


if __name__ == '__main__':
    main()
