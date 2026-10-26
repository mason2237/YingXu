"""Persist only the embedded-subtitle language rule, separately from appearance."""
import json
from PySide6.QtCore import QSettings
from ..embedded_subtitles import DEFAULT_OPTIONS, LANGUAGES
from .protocol import ProtocolError

KEY = "subtitles/embedded/v1"


class EmbeddedSettings:
    def __init__(self, settings=None):
        self.settings = settings if settings is not None else QSettings("YingXu", "SubtitleOrganizer")
        self.options = dict(DEFAULT_OPTIONS)
        try:
            value = self.settings.value(KEY, "")
            if value:
                data = json.loads(value)
                if set(data) == {"enabled", "language"} and type(data["enabled"]) is bool and data["language"] in LANGUAGES:
                    self.options = data
            elif settings is None:
                preference = str(QSettings("YingXu", "SubtitleDiscovery").value("language", "bilingual")).casefold()
                self.options["language"] = {"simplified":"simplified", "traditional":"traditional", "english":"english",
                    "zh-hans":"simplified", "zh-hant":"traditional", "en":"english"}.get(preference,"chinese")
        except (TypeError, ValueError, KeyError): pass

    def update(self, options):
        if set(options) != {"enabled", "language"} or type(options["enabled"]) is not bool or options["language"] not in LANGUAGES:
            raise ProtocolError("INVALID_REQUEST", "内嵌字幕语言设置无效。")
        self.settings.setValue(KEY, json.dumps(options))
        self.settings.sync()
        if self.settings.status() != QSettings.Status.NoError:
            raise ProtocolError("SAVE_FAILED", "字幕语言设置未能保存，当前计划保持不变。")
        self.options = dict(options)
