"""Run: python tests/alert_center_browser_smoke.py --base-url http://127.0.0.1:8787"""
import argparse

from playwright.sync_api import sync_playwright


def verify(page, base_url):
    # Isolate the notification runtime from live market-data rerenders while
    # loading the real shipped styles and enhancement script from the server.
    page.route('**/__alert_center_fixture__', lambda route: route.fulfill(
        content_type='text/html', body=f'''<!doctype html><html><head>
        <link rel="stylesheet" href="{base_url}/styles.css">
        <link rel="stylesheet" href="{base_url}/notification-phase2.css">
        </head><body><section id="alertCenter" class="alert-center">
        <div id="alertFilterRow"></div><div id="alertList" class="alert-list"></div>
        </section><div id="alertToast" class="alert-toast" hidden></div>
        <script src="{base_url}/notification-phase2.js"></script></body></html>'''))
    page.goto(base_url.rstrip('/') + '/__alert_center_fixture__', wait_until='load')
    page.wait_for_selector('.phase2-toolbar', state='attached')
    page.evaluate("""() => {
      const list = document.querySelector('#alertList');
      list.innerHTML = '<div class="alert-empty">ไม่มี alert ในหมวดนี้ตอนนี้ · ลอง Scan Now หรือเปลี่ยน filter</div>';
      document.querySelector('#alertToast').hidden = true;
    }""")
    page.wait_for_function("document.querySelector('[data-phase2-filter=unread]').textContent === 'Unread 0'")
    for status in ('all', 'unread', 'priority', 'all'):
        page.locator(f'[data-phase2-filter="{status}"]').evaluate('(button) => button.click()')
        assert page.locator('#alertList > .alert-empty').count() == 1
        assert page.locator('#alertList [data-phase2-enhanced]').count() == 0
        assert page.locator('#alertList .phase2-alert-actions').count() == 0
        assert page.locator('[data-phase2-filter=priority]').inner_text() == 'Priority 0'
    assert page.locator('#alertList').evaluate("node => getComputedStyle(node, '::after').content") in ('none', 'normal')
    assert page.locator('#alertToast').evaluate("node => getComputedStyle(node).display") == 'none'
    assert page.locator('.alert-empty').first.evaluate("node => getComputedStyle(node, '::before').content") in ('none', 'normal')
    # Toast content remains usable when explicitly shown, then disappears again.
    page.locator('#alertToast').evaluate("node => { node.textContent = 'Alert fixture'; node.hidden = false; }")
    if page.viewport_size['width'] > 767:
        assert page.locator('#alertToast').is_visible()
    page.locator('#alertToast').evaluate('node => { node.hidden = true; node.textContent = ""; }')
    page.evaluate("""() => {
      document.querySelector('#alertList').innerHTML =
        '<button class="alert-item action" data-alert-id="ui-regression-fixture" data-ticker="NVDA">NVDA ACTIONABLE</button>';
    }""")
    page.wait_for_selector('#alertList > [data-phase2-enhanced]', state='attached')
    assert page.locator('#alertList .phase2-alert-actions').count() == 1
    assert page.locator('[data-phase2-filter=unread]').inner_text() == 'Unread 1'
    page.locator('[data-phase2-action=mark-all-read]').evaluate('(button) => button.click()')
    page.locator('[data-phase2-filter=unread]').evaluate('(button) => button.click()')
    page.wait_for_selector('#alertList > .phase2-empty-state', state='attached')
    assert page.locator('#alertList > .alert-item').evaluate('node => getComputedStyle(node).display') == 'none'
    assert page.locator('#alertList > .alert-empty').count() == 1
    page.locator('[data-phase2-filter=all]').evaluate('(button) => button.click()')
    assert page.locator('#alertList > .phase2-empty-state').count() == 0
    page.locator('[data-phase2-action=dismiss]').evaluate('(button) => button.click()')
    page.wait_for_selector('#alertList > .phase2-empty-state', state='attached')
    assert page.locator('#alertList > .alert-empty').count() == 1
    assert page.locator('[data-phase2-filter=unread]').inner_text() == 'Unread 0'
    # A canonical rerender replaces the filter placeholder with a single base empty state.
    page.evaluate("document.querySelector('#alertList').innerHTML = '<div class=alert-empty>ไม่มี alert ในหมวดนี้ตอนนี้</div>'")
    page.wait_for_function("document.querySelector('[data-phase2-filter=priority]').textContent === 'Priority 0'")
    assert page.locator('#alertList > .alert-empty').count() == 1
    assert page.locator('#alertList [data-phase2-enhanced]').count() == 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-url', required=True)
    parser.add_argument('--chromium', default='/usr/bin/chromium')
    args = parser.parse_args()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=args.chromium, headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'])
        try:
            for width in (1440, 390):
                page = browser.new_page(viewport={'width': width, 'height': 1000})
                try:
                    verify(page, args.base_url)
                    print(f'Alert Center passed at width {width}: empty, filters, read, dismiss, rerender, toast')
                except Exception:
                    page.screenshot(path=f'/tmp/alert-center-failure-{width}.png', full_page=True)
                    raise
                finally:
                    page.close()
        finally:
            browser.close()


if __name__ == '__main__':
    main()
