"""Draw Me a Fact — autonomous production studio engine.

Public entry points:
    dmf.pipeline.run_episode(...)     full film: script -> voice -> frames -> mux -> QA
    dmf.qa_gate.run_checks(...)       the §9 QA gate on an existing artefact
    dmf.publish.publish_episode(...)  YouTube Shorts / Instagram Reels upload
"""

from __future__ import annotations

__version__ = "1.1.0"
