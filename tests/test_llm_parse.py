import json

from keeta_voc.llm import build_request, label_one, parse_response, response_schema, system_prompt, user_prompt
from keeta_voc.taxonomy import label_names


def test_parse_ok():
    assert parse_response('{"labels": ["app_ux", "delivery_time"]}') == ("ok", ["delivery_time", "app_ux"], None)


def test_parse_bad_json_is_recorded_not_dropped():
    st, labels, err = parse_response('{"labels": ["app_ux"')
    assert st == "bad_json" and labels is None and err
    assert parse_response('["app_ux"]')[0] == "bad_json"
    assert parse_response('{"label": ["app_ux"]}')[0] == "bad_json"


def test_parse_bad_labels():
    assert parse_response('{"labels": []}')[0] == "bad_labels"
    assert parse_response('{"labels": ["late_delivery"]}')[0] == "bad_labels"
    assert parse_response('{"labels": ["other", "app_ux"]}')[0] == "bad_labels"


def test_schema_enum_is_the_taxonomy():
    assert response_schema()["properties"]["labels"]["items"]["enum"] == list(label_names())


def test_prompt_lists_every_label_and_truncates():
    sp = system_prompt()
    for n in label_names():
        assert f"- {n}:" in sp
    up = user_prompt("t", "x" * 5000)
    assert up.endswith("[...]") and len(up) < 1600


def test_request_is_deterministic_cpu():
    req = build_request("m", "t", "x")
    assert req["options"]["temperature"] == 0 and req["options"]["num_gpu"] == 0
    assert req["format"] == response_schema()


def test_label_one_records_everything():
    rec = label_one("m", "k1", "t", "late", call=lambda req: {"message": {"content": '{"labels": ["delivery_time"]}'}})
    assert rec["status"] == "ok" and rec["labels"] == ["delivery_time"] and len(rec["prompt_sha256"]) == 64
    rec = label_one("m", "k2", "t", "late", call=lambda req: {"message": {"content": "nonsense"}})
    assert rec["status"] == "bad_json" and rec["labels"] is None and rec["raw_response"] == "nonsense"

    def boom(req):
        raise TimeoutError("slow")
    rec = label_one("m", "k3", "t", "late", call=boom)
    assert rec["status"] == "http_error" and "slow" in rec["error"]
    json.dumps(rec)
