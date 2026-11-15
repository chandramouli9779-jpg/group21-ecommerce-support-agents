from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from agents import learning
from contracts import Result, Status

APP = Path(__file__).resolve().parents[1] / "app.py"


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr(learning, "COUNTS_FILE", tmp_path / "counts.json")
    return AppTest.from_file(str(APP), default_timeout=20).run()


def button(app, label):
    return next(b for b in app.button if b.label == label)


def run_offline(app):
    app.checkbox[0].uncheck().run()
    button(app, "Run Comparison").click().run()
    assert not app.exception
    return app


def test_initial_render(app):
    assert not app.exception
    assert app.selectbox[0].value == "A"
    assert "comparison" not in app.session_state


@pytest.mark.parametrize("scenario", list("ABCD"))
def test_six_rows_and_not_run_explicit(app, scenario):
    app.selectbox[0].select(scenario).run()
    run_offline(app)
    results = app.session_state["comparison"]["results"]
    assert len(results) == 6
    assert all(r.case_id == scenario for r in results)
    assert results[-1].status == Status.NOT_RUN
    assert len(app.dataframe[0].value) == 6


def test_scenario_model_and_llm_toggle_clear(app):
    run_offline(app)
    app.selectbox[0].select("B").run()
    assert "comparison" not in app.session_state
    button(app, "Run Comparison").click().run()
    app.text_input[0].set_value("qwen3:1.7b").run()
    assert "comparison" not in app.session_state
    button(app, "Run Comparison").click().run()
    app.checkbox[0].check().run()
    assert "comparison" not in app.session_state


def test_two_feedback_steps_persist_once_and_switch(app):
    run_offline(app)
    path = learning.COUNTS_FILE
    for failure in (4, 5):
        button(app, "Record failure").click().run()
        assert not app.exception
        assert "comparison" not in app.session_state
        assert any("Feedback saved" in message.value for message in app.success)
        assert learning.load_counts(path)["timely_nonreceipt|delivery_investigation"]["failure"] == failure
        app.run()
        assert learning.load_counts(path)["timely_nonreceipt|delivery_investigation"]["failure"] == failure
        button(app, "Run Comparison").click().run()
    assert app.session_state["comparison"]["results"][4].action.value == "human_review"
    button(app, "Reset learning history").click().run()
    assert "comparison" not in app.session_state
    assert learning.load_counts(path) == learning.seed_counts()
    assert "last_feedback" not in app.session_state


def test_mechanism_explanations_and_weight_sensitivity(app):
    run_offline(app)
    assert any(h.value == "Why decisions differ" for h in app.subheader)
    assert any("risk-heavy weights" in caption.value and "human_review" in caption.value
               for caption in app.caption)
    assert len(app.dataframe) > 1
    app.selectbox[0].select("B").run()
    button(app, "Run Comparison").click().run()
    assert any("without calculating its age" in message.value for message in app.info)


def test_llm_failure_does_not_hide_classical(app, monkeypatch):
    from agents import llm
    monkeypatch.setattr(llm, "run", lambda case, model: Result(agent="LLM", case_id=case.case_id,
                                                             status=Status.ERROR, rationale="Unavailable", model=model))
    button(app, "Run Comparison").click().run()
    assert not app.exception
    assert len(app.session_state["comparison"]["results"]) == 6
    assert app.session_state["comparison"]["results"][-1].status == Status.ERROR
