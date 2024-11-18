from pg_channel import plsql


def test_updates_params():
    script0 = plsql("table")
    script1 = plsql("table", 7, {"event1": ("field1",), "_event2": ["field2"]})
    script2 = plsql("table", 5, {"event1": ("field1", "field2"), "event2": ["field2", "field3"]})
    print(script0, script1, script2)
    assert script0 and script1 and script2, "Bad update params"
