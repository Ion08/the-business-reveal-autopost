import unittest
import os
from datetime import date, datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

import publish


class ScheduleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.posts = publish.load_posts()

    def test_all_posts_have_distinct_slots_and_five_images(self):
        self.assertEqual(len(self.posts), 30)
        self.assertEqual(len({(p["date"], p["slot"]) for p in self.posts}), 30)
        self.assertEqual(sum(len(p["images"]) for p in self.posts), 150)

    def test_first_and_last_slots(self):
        zone = ZoneInfo("Europe/Chisinau")
        first = publish.current_post(self.posts, datetime(2026, 10, 4, 9, 0, tzinfo=zone))
        last = publish.current_post(self.posts, datetime(2026, 10, 13, 19, 0, tzinfo=zone))
        self.assertEqual(first["brand"], "Costco")
        self.assertEqual(last["brand"], "Dollar General")

    def test_no_backfill_or_off_schedule_publish(self):
        zone = ZoneInfo("Europe/Chisinau")
        self.assertIsNone(publish.current_post(self.posts, datetime(2026, 10, 4, 9, 21, tzinfo=zone)))
        self.assertIsNone(publish.current_post(self.posts, datetime(2026, 10, 14, 9, 0, tzinfo=zone)))

    def test_start_date_can_move_without_changing_post_order(self):
        zone = ZoneInfo("Europe/Chisinau")
        first = publish.current_post(self.posts, datetime(2026, 10, 8, 9, 0, tzinfo=zone), date(2026, 10, 8))
        self.assertEqual(first["brand"], "Costco")
        self.assertIsNone(publish.current_post(self.posts, datetime(2026, 10, 4, 9, 0, tzinfo=zone), date(2026, 10, 8)))

    def test_blank_start_date_is_safe_outside_a_slot(self):
        zone = ZoneInfo("Europe/Chisinau")
        with patch.dict(os.environ, {"CAMPAIGN_START_DATE": ""}):
            self.assertEqual(publish.run(datetime(2026, 10, 4, 10, 34, tzinfo=zone), live=True), 0)


class IdempotencyTests(unittest.TestCase):
    def setUp(self):
        self.post = {"id": "test-post"}

    @patch("publish.save_state")
    def test_published_post_is_skipped(self, save):
        state = {"test-post": {"instagram": {"status": "published", "media_id": "123"}}}
        publish.publish_platform(None, state, self.post, "instagram", lambda: self.fail("prepare called"), lambda _: self.fail("publish called"))
        save.assert_not_called()

    @patch("publish.save_state")
    def test_uncertain_attempt_is_not_retried(self, save):
        state = {"test-post": {"instagram": {"status": "attempting"}}}
        with self.assertRaises(publish.PublishError):
            publish.publish_platform(None, state, self.post, "instagram", lambda: self.fail("prepare called"), lambda _: self.fail("publish called"))
        save.assert_not_called()

    @patch("publish.save_state")
    def test_failed_publish_leaves_reservation(self, save):
        state = {}

        def fail(_):
            raise publish.PublishError("network response lost")

        with self.assertRaises(publish.PublishError):
            publish.publish_platform(None, state, self.post, "instagram", lambda: "container-1", fail)
        self.assertEqual(state["test-post"]["instagram"]["status"], "attempting")
        save.assert_called_once()

    @patch("publish.save_state")
    def test_success_records_media_id(self, save):
        state = {}
        publish.publish_platform(None, state, self.post, "facebook", lambda: ["photo-1"], lambda _: "post-1")
        self.assertEqual(state["test-post"]["facebook"]["media_id"], "post-1")
        self.assertEqual(save.call_count, 2)


if __name__ == "__main__":
    unittest.main()
