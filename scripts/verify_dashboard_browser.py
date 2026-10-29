"""Read-only browser checks and screenshots, restricted to synthetic demo mode."""
from pathlib import Path
import json
import os
import re

from playwright.sync_api import sync_playwright


def main():
    directory = Path('docs/screenshots')
    directory.mkdir(parents=True, exist_ok=True)
    executable = os.getenv('DASHBOARD_BROWSER_EXECUTABLE')
    if not executable:
        executable = next((str(p) for p in [
            Path('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'),
            Path('C:/Program Files/Google/Chrome/Application/chrome.exe')]
                           if p.is_file()), None)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, **({'executable_path': executable} if executable else {}))
        context = browser.new_context(viewport={'width': 1440, 'height': 1080}, accept_downloads=True)
        page = context.new_page()
        page.set_default_timeout(10000)
        frames = []
        page.on('websocket', lambda ws: ws.on('framereceived', lambda data: frames.append(data)))
        page.goto(os.getenv('DASHBOARD_BROWSER_URL', 'http://127.0.0.1:18501'))
        banner = 'Synthetic demonstration data — all subjects, measurements and labels are fictional.'
        page.get_by_text(banner, exact=True).wait_for(timeout=30000)
        assert page.get_by_test_id('stMetricValue').first.inner_text() == '60'
        page.locator('canvas').first.wait_for(state='visible', timeout=7000)
        captures = []
        for label, filename in [('Overview', 'overview'), ('Feature Explorer', 'feature-explorer'),
                                ('Data Quality', 'data-quality'), ('Dataset Export', 'dataset-export')]:
            page.set_viewport_size({'width': 1440, 'height': 1800 if label == 'Data Quality' else 1080})
            page.get_by_test_id('stSidebar').get_by_text(label, exact=True).click()
            page.get_by_role('heading', name=label, exact=True).wait_for(timeout=15000)
            page.get_by_text(banner, exact=True).wait_for()
            # Wait for the rerun to finish before inspecting the view.
            page.get_by_test_id('stStatusWidget').wait_for(state='hidden', timeout=20000)
            assert page.get_by_test_id('stException').count() == 0
            assert page.get_by_text('This view could not be loaded.', exact=False).count() == 0
            assert not re.search(r'P\d{2}-(?:FAKE-)?\d+', page.locator('body').inner_text())
            if label == 'Data Quality':
                page.locator('canvas').first.wait_for(state='visible', timeout=7000)
            if label == 'Dataset Export':
                with page.expect_download() as event:
                    page.get_by_role('button', name='Download CSV', exact=True).click()
                download = event.value
                text = Path(download.path()).read_text(encoding='utf-8')
                assert len(text.splitlines()) == 61
                assert not re.search(r'P\d{2}-(?:FAKE-)?\d+', text)
                assert 'id_anonymat' not in text and 'synthetic-' not in text
                assert 'SIM_Rea_cor_pos_5.0' in text
            path = directory / f'{filename}.png'
            page.screenshot(path=str(path), full_page=True)
            captures.append(str(path))
        page.get_by_test_id('stSidebar').get_by_text('Overview', exact=True).click()
        page.get_by_role('heading', name='Overview', exact=True).wait_for()
        collapse = page.locator('[data-testid="stSidebarCollapseButton"] button')
        if collapse.count() and collapse.is_visible():
            collapse.click()
        page.set_viewport_size({'width': 390, 'height': 844})
        page.get_by_test_id('stSidebar').wait_for(state='hidden', timeout=5000)
        page.screenshot(path=str(directory / 'overview-mobile.png'), full_page=True)
        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth + 2')
        # Neither original participant codes nor the server API key may enter
        # Streamlit websocket messages, including hidden widget keys.
        payload = b''.join(item.encode() if isinstance(item, str) else item for item in frames)
        assert not re.search(rb'P\d{2}-(?:FAKE-)?\d+', payload)
        from dotenv import load_dotenv
        load_dotenv('.env.demo')
        key = os.getenv('DEMO_API_KEY', '')
        assert not key or key.encode() not in payload
        report = {'pages': 4, 'synthetic_only': True, 'csv_records': 60,
                  'desktop_width': 1440, 'mobile_width': 390,
                  'browser_identifier_and_api_key_leak_check': 'passed', 'screenshots': captures}
        Path('.release-audit').mkdir(exist_ok=True)
        Path('.release-audit/dashboard_browser_verification.json').write_text(
            json.dumps(report, indent=2), encoding='utf-8')
        print(json.dumps(report, indent=2))
        context.close()
        browser.close()


if __name__ == '__main__':
    main()
