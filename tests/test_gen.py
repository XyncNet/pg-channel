from pg_channel import plsql, Act


def test_updates_params():
    script0 = plsql("user")
    script1 = plsql("order", Act.NEW+Act.UPD, {"change": ["status"]})
    script2 = plsql("table3", Act.NEW+Act.DEL, {"event1": ("field1", "field2"), "event2": ["field2", "field3"]})
    print(script0, script1, script2)
    assert script0 and script1 and script2, "Bad update params"

test_updates_params()