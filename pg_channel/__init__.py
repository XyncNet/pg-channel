from enum import IntEnum


class Act(IntEnum):
    DEL = 1
    NEW = 2
    UPD = 4


def plsql(table: str, ops: int = 7, updates: dict[str, tuple | list] = None):
    def send(chnl, rtrns):
        return f"PERFORM pg_notify('{chnl}', {rtrns});"

    rtrn_all = "row_to_json(NEW)::varchar"
    if updates:
        conds = []
        for fset, fields in updates.items():
            isfirst = list(updates)[0] == fset
            if fset.startswith("_"):
                els = "ELS"
                fset = fset[1:]
            else:
                els = ""
            prevendif = "" if isfirst or els else "END IF;\n\t"
            opr = "AND" if isinstance(fields, tuple) else "OR"
            channel = table + "s_upd_" + fset
            cond = f" {opr} ".join([f"OLD.{field}!=NEW.{field}" for field in fields])
            conds.append(f"{prevendif}{els}IF {cond} THEN\n\t\t{send(channel, rtrn_all)}")
        upd = "\n\t".join(conds) + "\n\tEND IF;"
    else:
        upd = send(table + "s_upd", rtrn_all)
    fns: dict[Act, str] = {
        Act.UPD: f"""
CREATE OR REPLACE FUNCTION {table}_upd() returns trigger as ${table}_upd_trg$
BEGIN
    {upd}
    RETURN NULL;
END
${table}_upd_trg$ LANGUAGE plpgsql;
CREATE OR REPLACE TRIGGER {table}_upd AFTER UPDATE ON "{table}" FOR EACH ROW EXECUTE FUNCTION {table}_upd();
""",
        Act.NEW: f"""
CREATE OR REPLACE FUNCTION {table}_new() returns trigger as ${table}_new_trg$
BEGIN
    PERFORM pg_notify('{table}s_new', row_to_json(NEW)::varchar);
    RETURN NULL;
END
${table}_new_trg$ LANGUAGE plpgsql;
CREATE OR REPLACE TRIGGER {table}_new AFTER INSERT ON "{table}" FOR EACH ROW EXECUTE FUNCTION {table}_new();
""",
        Act.DEL: f"""
CREATE OR REPLACE FUNCTION {table}_del() returns trigger as ${table}_del_trg$
BEGIN
    PERFORM pg_notify('{table}s_del', OLD.id::varchar);
    RETURN NULL;
END
${table}_del_trg$ LANGUAGE plpgsql;
CREATE OR REPLACE TRIGGER {table}_del AFTER DELETE ON "{table}" FOR EACH ROW EXECUTE FUNCTION {table}_del();
""",
    }
    return "".join(fn for op, fn in fns.items() if ops & op)
