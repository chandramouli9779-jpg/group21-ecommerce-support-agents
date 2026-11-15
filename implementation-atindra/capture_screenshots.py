"""Optional browser evidence. Run Streamlit on port 8517 first.

Default captures disable live inference. --live runs real selected cases once;
saved evidence is never replayed. --learning temporarily resets feedback and
restores the original counts file, including its absence, even on failure.
Requires optional Playwright and an installed Google Chrome browser.
"""
from pathlib import Path
import argparse
from playwright.sync_api import sync_playwright


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://localhost:8517")
    parser.add_argument("--live", action="store_true", help="Run one real UI comparison per selected case")
    parser.add_argument("--live-cases", nargs="+", choices=list("ABCD"), default=["A"])
    parser.add_argument("--learning", action="store_true", help="Capture the three-stage offline learning demo")
    parser.add_argument("--skip-offline", action="store_true", help="Keep existing desktop/mobile captures")
    args = parser.parse_args()
    destination = Path(__file__).with_name("evidence")
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1100}, device_scale_factor=1)
        page.goto(args.url)
        page.get_by_text("Run real local LLM", exact=True).click()
        if not args.skip_offline:
            for case_id in "ABCD":
                page.get_by_role("combobox", name="Scenario").click()
                page.get_by_role("option", name=case_id, exact=True).click()
                page.get_by_role("button", name="Run Comparison", exact=True).click()
                page.get_by_text("Fixture target:").wait_for(timeout=30000)
                page.get_by_role("button", name="Download this comparison").wait_for()
                page.wait_for_timeout(1000)
                page.screenshot(path=str(destination / f"scenario_{case_id}_offline.png"), full_page=True)
            page.get_by_role("combobox", name="Scenario").click()
            page.get_by_role("option", name="A", exact=True).click()
            page.get_by_role("button", name="Run Comparison", exact=True).click()
            page.get_by_text("Fixture target:").wait_for(timeout=30000)
            page.get_by_text("Utility-Based: delivery_investigation", exact=True).click()
            page.locator("summary").filter(has_text="Learning:").click()
            page.get_by_text("risk-heavy weights", exact=False).wait_for()
            page.screenshot(path=str(destination / "mechanisms_A_offline.png"), full_page=True)
        if args.live:
            page.get_by_text("Run real local LLM", exact=True).click()
            for case_id in args.live_cases:
                page.get_by_role("combobox", name="Scenario").click()
                page.get_by_role("option", name=case_id, exact=True).click()
                page.get_by_text("Run Comparison to inspect six outcomes.", exact=False).wait_for()
                page.get_by_role("button", name="Run Comparison", exact=True).click()
                page.locator("summary").filter(has_text="LLM (Ollama + tools):").wait_for(timeout=900000)
                page.locator("summary").filter(has_text="LLM (Ollama + tools):").click()
                page.wait_for_timeout(1000)
                page.screenshot(path=str(destination / f"scenario_{case_id}_live.png"), full_page=True)
                with page.expect_download() as downloaded:
                    page.get_by_role("button", name="Download this comparison").click()
                downloaded.value.save_as(str(destination / f"final-ui-{case_id}-comparison.jsonl"))
                print(f"Saved real UI case {case_id}", flush=True)
        if args.learning:
            page.set_viewport_size({"width": 1440, "height": 6000})
            counts_path = destination.parent / "runtime" / "learning_counts.json"
            original = counts_path.read_bytes() if counts_path.exists() else None
            runtime_existed = counts_path.parent.exists()
            try:
                page.goto(args.url)
                page.get_by_text("Run real local LLM", exact=True).click()
                page.get_by_role("button", name="Reset learning history", exact=True).click()
                for stage in range(3):
                    page.get_by_role("button", name="Run Comparison", exact=True).click()
                    page.get_by_role("button", name="Download this comparison").wait_for()
                    learning = page.locator("summary").filter(has_text="Learning:")
                    if not learning.evaluate("el => el.parentElement.open"):
                        learning.click()
                    page.get_by_role("button", name="Record failure", exact=True).wait_for()
                    page.wait_for_timeout(1000)
                    page.screenshot(path=str(destination / f"learning_A_stage_{stage}.png"), full_page=True,
                                    mask=[page.get_by_text("Persistent history:", exact=False)])
                    with page.expect_download() as downloaded:
                        page.get_by_role("button", name="Download this comparison").click()
                    downloaded.value.save_as(str(destination / f"learning_A_stage_{stage}.jsonl"))
                    if stage < 2:
                        page.get_by_role("button", name="Record failure", exact=True).click()
                        page.get_by_text("Run Comparison to inspect six outcomes.", exact=False).wait_for()
            finally:
                if original is None:
                    counts_path.unlink(missing_ok=True)
                else:
                    counts_path.write_bytes(original)
                if not runtime_existed and counts_path.parent.exists():
                    counts_path.parent.rmdir()
                print("Restored original learning state", flush=True)
        if not args.skip_offline:
            page = browser.new_page(viewport={"width": 390, "height": 844})
            page.goto(args.url)
            page.get_by_role("heading", name="Evidence Before Action").wait_for()
            page.screenshot(path=str(destination / "mobile_initial.png"), full_page=True)
            page.get_by_role("button", name="Expand sidebar").click()
            page.get_by_text("Run real local LLM", exact=True).click()
            page.get_by_test_id("stSidebarCollapseButton").click()
            page.get_by_role("button", name="Run Comparison", exact=True).click()
            page.get_by_text("Fixture target:").wait_for(timeout=30000)
            page.get_by_role("button", name="Download this comparison").wait_for()
            page.wait_for_timeout(1000)
            page.screenshot(path=str(destination / "scenario_A_mobile_offline.png"), full_page=True)
        browser.close()
