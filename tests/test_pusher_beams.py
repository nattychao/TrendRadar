"""Pusher Beams payload: one push per report, within the APNs size limit."""

import json
import unittest

from trendradar.notification.senders import (
    PUSHER_BEAMS_PAYLOAD_LIMIT,
    build_pusher_beams_payload,
    describe_pusher_beams_payload,
)


def _report(count, title_length=10):
    titles = [
        {
            "title": f"热点{i}" + "字" * title_length,
            "source_name": "微博",
            "url": f"https://example.com/{i}",
            "mobile_url": f"https://m.example.com/{i}" if i % 2 else "",
            "is_new": i == 0,
        }
        for i in range(count)
    ]
    return {"stats": [{"word": "科技", "titles": titles}]}


def _apns_size(payload):
    return len(json.dumps(payload["apns"], ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


class PusherBeamsPayloadTests(unittest.TestCase):
    def test_nothing_to_push(self):
        self.assertIsNone(build_pusher_beams_payload({"stats": []}, "当前榜单", "hotspot"))

    def test_alert_and_items(self):
        payload = build_pusher_beams_payload(_report(5), "当前榜单", "hotspot", mode="current")
        self.assertEqual(payload["interests"], ["hotspot"])
        alert = payload["apns"]["aps"]["alert"]
        self.assertEqual(alert["title"], "热点 · 当前榜单")
        self.assertEqual(alert["body"].count("•"), 3)
        self.assertIn("等 5 条", alert["body"])

        hotspot = payload["apns"]["hotspot"]
        self.assertEqual(hotspot["total"], 5)
        self.assertEqual(len(hotspot["items"]), 5)
        first, second = hotspot["items"][0], hotspot["items"][1]
        self.assertTrue(first["n"])
        self.assertEqual(first["u"], "https://example.com/0")  # no mobile link: the page's
        self.assertEqual(second["u"], "https://m.example.com/1")  # the mobile link first
        self.assertEqual(first["k"], "科技")
        self.assertEqual(first["s"], "微博")

    def test_duplicates_across_keyword_groups_once(self):
        report = _report(2)
        report["stats"].append(dict(report["stats"][0], word="其他"))
        payload = build_pusher_beams_payload(report, "当前榜单", "hotspot")
        self.assertEqual(payload["apns"]["hotspot"]["total"], 2)

    def test_platform_lists_follow_the_keyword_matches(self):
        standalone = {"platforms": [{"id": "toutiao", "name": "今日头条", "items": [
            {"title": "头条一", "url": "https://toutiao.com/1", "mobileUrl": "https://m.toutiao.com/1"},
            {"title": "热点0字字字字字字字字字字", "url": "https://example.com/0", "mobileUrl": ""},
        ]}]}
        payload = build_pusher_beams_payload(_report(1), "当前榜单", "hotspot", standalone_data=standalone)
        items = payload["apns"]["hotspot"]["items"]
        self.assertEqual([item["k"] for item in items], ["科技", "今日头条"])
        self.assertEqual(items[1]["u"], "https://m.toutiao.com/1")
        self.assertEqual(items[1]["s"], "今日头条")

    def test_stays_within_the_apns_limit(self):
        payload = build_pusher_beams_payload(_report(200, title_length=30), "全天汇总", "hotspot")
        self.assertLessEqual(_apns_size(payload), PUSHER_BEAMS_PAYLOAD_LIMIT)
        hotspot = payload["apns"]["hotspot"]
        self.assertEqual(hotspot["total"], 200)
        self.assertLess(len(hotspot["items"]), 200)
        self.assertGreater(len(hotspot["items"]), 0)


    def test_the_log_shows_what_the_phone_gets(self):
        payload = build_pusher_beams_payload(_report(2), "当前榜单", "hotspot")
        text = describe_pusher_beams_payload(payload)
        self.assertIn("标题：热点 · 当前榜单", text)
        self.assertIn("订阅：hotspot", text)
        self.assertIn("附带条目：2/2", text)
        self.assertIn("1. [科技] 热点0字字字字字字字字字字（微博） 🆕", text)
        self.assertIn("https://m.example.com/1", text)


if __name__ == "__main__":
    unittest.main()
