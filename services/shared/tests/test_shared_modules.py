"""
Юнит-тесты общих модулей: коды отметки, подпись MAX initData, серии, настроение.
"""
import time
from datetime import datetime, timedelta, timezone

import pytest

from services.shared import attendance_codes as ac
from services.shared.character_mood import growth_stage, mood_from_satisfaction
from services.shared.max_auth import InitDataError, extract_max_user_id, sign_init_data, validate_init_data
from services.shared.models.lesson import LessonMissStatus
from services.shared.streaks import ATTENDED, compute_streaks
from services.shared.timeutil import local_to_utc


NOW = datetime(2026, 10, 1, 10, 0, 7, tzinfo=timezone.utc)


class TestAttendanceCodes:
    def test_code_is_four_digits_and_stable_within_window(self):
        code = ac.current_lesson_code("secret", 7, NOW)
        assert len(code) == 4 and code.isdigit()
        assert ac.current_lesson_code("secret", 7, NOW + timedelta(seconds=1)) == code

    def test_current_and_previous_window_accepted(self, monkeypatch):
        monkeypatch.setenv("LESSON_CODE_WINDOW_SECONDS", "30")
        code = ac.current_lesson_code("secret", 7, NOW)
        assert ac.verify_lesson_code("secret", 7, code, NOW)
        assert ac.verify_lesson_code("secret", 7, code, NOW + timedelta(seconds=30))
        assert not ac.verify_lesson_code("secret", 7, code, NOW + timedelta(seconds=61))

    def test_code_bound_to_lesson_and_secret(self):
        window = ac.current_window(NOW)
        codes_lessons = {ac.lesson_code("secret", lesson_id, window) for lesson_id in range(1, 30)}
        assert len(codes_lessons) > 20  # коды разных занятий различаются
        code = ac.lesson_code("secret", 7, window)
        other_secret_ok = ac.verify_lesson_code("other", 7, code, NOW)
        # Совпадение возможно с вероятностью ~1/5000 — фиксированные входы проверены
        assert not other_secret_ok

    @pytest.mark.parametrize("bad", [None, "", "12", "abcd", "12345"])
    def test_rejects_malformed(self, bad):
        assert not ac.verify_lesson_code("secret", 7, bad, NOW)

    def test_payload_roundtrip_and_url_parsing(self):
        payload = ac.build_checkin_payload(12, "0457")
        assert payload == "att-12-0457"
        assert ac.parse_checkin_payload(payload) == (12, "0457")
        assert ac.parse_checkin_payload("https://max.ru/matrix_bot?startapp=att-12-0457") == (12, "0457")
        assert ac.parse_checkin_payload("something else") is None
        links = ac.build_deep_links("@matrix_bot", payload)
        assert links["startapp_url"] == "https://max.ru/matrix_bot?startapp=att-12-0457"
        assert ac.build_deep_links(None, payload)["startapp_url"] is None


class TestMaxInitData:
    TOKEN = "test-bot-token"

    def _fields(self, **overrides):
        fields = {
            "auth_date": int(time.time()),
            "query_id": "q1",
            "user": {"id": 555, "first_name": "Иван"},
            "start_param": "att-3-1234",
        }
        fields.update(overrides)
        return fields

    def test_valid_signature(self):
        init_data = sign_init_data(self._fields(), self.TOKEN)
        data = validate_init_data(init_data, self.TOKEN)
        assert extract_max_user_id(data) == 555
        assert data["start_param"] == "att-3-1234"

    def test_tampered_field_rejected(self):
        init_data = sign_init_data(self._fields(), self.TOKEN).replace("att-3-1234", "att-3-9999")
        with pytest.raises(InitDataError):
            validate_init_data(init_data, self.TOKEN)

    def test_wrong_token_rejected(self):
        init_data = sign_init_data(self._fields(), self.TOKEN)
        with pytest.raises(InitDataError):
            validate_init_data(init_data, "another-token")

    def test_expired_rejected(self):
        init_data = sign_init_data(self._fields(auth_date=int(time.time()) - 3 * 86400), self.TOKEN)
        with pytest.raises(InitDataError):
            validate_init_data(init_data, self.TOKEN)

    def test_missing_rejected(self):
        with pytest.raises(InitDataError):
            validate_init_data("", self.TOKEN)


class TestStreaks:
    def test_attended_sequence(self):
        assert compute_streaks([ATTENDED, ATTENDED, ATTENDED]) == (3, 3)

    def test_penalized_resets_current_keeps_best(self):
        statuses = [ATTENDED, ATTENDED, LessonMissStatus.PENALIZED, ATTENDED]
        assert compute_streaks(statuses) == (1, 2)

    def test_frozen_and_pending_do_not_break(self):
        statuses = [ATTENDED, LessonMissStatus.FROZEN, ATTENDED, LessonMissStatus.PENDING, ATTENDED]
        assert compute_streaks(statuses) == (3, 3)

    def test_empty(self):
        assert compute_streaks([]) == (0, 0)


class TestMoodAndTime:
    @pytest.mark.parametrize("value,code", [(100, "ecstatic"), (70, "happy"), (50, "neutral"), (25, "sad"), (0, "depressed")])
    def test_mood(self, value, code):
        assert mood_from_satisfaction(value)[0] == code

    def test_growth(self):
        assert growth_stage(1)[0] == "baby"
        assert growth_stage(4)[0] == "teen"
        assert growth_stage(9)[0] == "adult"

    def test_local_time_to_utc(self, monkeypatch):
        monkeypatch.setenv("APP_UTC_OFFSET_HOURS", "3")
        assert local_to_utc(datetime(2026, 10, 1, 13, 40)) == datetime(2026, 10, 1, 10, 40, tzinfo=timezone.utc)
