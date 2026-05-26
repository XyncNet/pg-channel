[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://github.com/pre-commit/pre-commit)

# pg-channel

> [Русская версия](./README.rus.md)

Generate ready-to-run PL/pgSQL scripts that wire up PostgreSQL `LISTEN`/`NOTIFY` channels for `INSERT` / `UPDATE` / `DELETE` events on a given table.

## Why this project

PostgreSQL's `LISTEN`/`NOTIFY` is the cheapest way to push row-level changes to application code (workers, websockets, cache invalidators, etc.) without polling. But writing trigger functions by hand is repetitive and error-prone:

- you need a separate trigger function per table per event;
- payload formatting must be consistent across services that consume the channel;
- on `UPDATE` you usually don't want the full row — you want the **diff** (which fields changed and from what to what);
- you often need conditional channels — e.g. notify only when specific fields change, with `AND` / `OR` logic between them.

`pg-channel` solves all of this with a single function `plsql()` that, from a table name and an optional dict describing update conditions, produces a complete PL/pgSQL script. Run the output once against your database — and the channels are live.

### Channel payload conventions

- `tables_new` — on `INSERT`, payload = the full new row as JSON (`row_to_json(NEW)`).
- `tables_del` — on `DELETE`, payload = `OLD.id` (as string).
- `tables_upd` (or `tables_upd_<event>`) — on `UPDATE`, payload = JSON array `[NEW.id, diff]`, where `diff` is an object of the form `{field_name: [old_value, new_value], ...}` containing **only changed fields**. If nothing changed, `diff` is `null`.

> The `del` channel intentionally sends only the id — a deleted row has no other useful state for consumers, and a numeric id keeps payloads small.

## Installation

```bash
pip install pg-channel
```

## Usage

```python
from pg_channel import plsql, Act
```

`plsql(table, ops=7, updates=None)` returns a `str` containing the full PL/pgSQL script. Execute it against your database with any client (`psycopg`, `asyncpg`, `psql -f`, a migration tool, etc.).

### Arguments

| name      | type                          | default | description                                                                                                                                            |
|-----------|-------------------------------|---------|--------------------------------------------------------------------------------------------------------------------------------------------------------|
| `table`   | `str`                         | —       | Table name. Used as-is for the channel prefix (`{table}s_*`) and is wrapped in double quotes inside the `CREATE TRIGGER` statement.                    |
| `ops`     | `int` (bitmask of `Act`)      | `7`     | Which triggers to generate. `Act.DEL=1`, `Act.NEW=2`, `Act.UPD=4`. Combine with bitwise OR. `7` = all three.                                            |
| `updates` | `dict[str, tuple \| list]`    | `None`  | Optional conditional routing for the update trigger. Keys are event names, values are field sets. See [Conditional update channels](#conditional-update-channels). |

### Examples

#### All three triggers, single update channel

```python
plsql("my_ad")
```

Fires:
- `my_ads_new` on insert,
- `my_ads_del` on delete,
- `my_ads_upd` on any update.

#### Only the update trigger

```python
plsql("my_ad", Act.UPD)   # same as plsql("my_ad", 4)
```

The generated update function looks like this:

```sql
CREATE OR REPLACE FUNCTION my_ad_upd() returns trigger as $my_ad_upd_trg$
    DECLARE
        diff jsonb;
    BEGIN
        SELECT jsonb_object_agg(key, jsonb_build_array(to_jsonb(OLD) -> key, value))
        INTO diff
        FROM jsonb_each(to_jsonb(NEW))
        WHERE value IS DISTINCT FROM (to_jsonb(OLD) -> key);

        PERFORM pg_notify('my_ads_upd', jsonb_build_array(NEW.id, diff)::varchar);
        RETURN NULL;
    END
    $my_ad_upd_trg$ LANGUAGE plpgsql;
CREATE OR REPLACE TRIGGER my_ad_upd AFTER UPDATE ON "my_ad" FOR EACH ROW EXECUTE FUNCTION my_ad_upd();
```

A consumer of `my_ads_upd` will receive payloads like:

```json
[42, {"status": ["draft", "published"], "price": [100, 120]}]
```

### Conditional update channels

The `updates` argument splits the single `tables_upd` channel into several named sub-channels, each fired only when its field condition is met.

- **Key** — event name; the channel becomes `{table}s_upd_{event}`.
- **Value** — fields that must change for the event to fire:
  - `list` → **OR** (any of the listed fields changed),
  - `tuple` → **AND** (all of the listed fields changed).
- **Key prefixed with `_`** → the branch is emitted as `ELSIF` instead of an independent `IF`, so it fires only when no earlier branch matched (useful for mutually exclusive events).

#### One specific field

```python
plsql("order", 7, {"change": ["status"]})
```

Fires `orders_upd_change` only when `order.status` changes.

#### AND / OR mix

```python
plsql("table3", 5, {
    "event1": ("field1", "field2"),   # tuple → AND
    "event2": ["field2", "field3"],   # list  → OR
})
```

Generates two independent `IF` blocks — both can fire on the same row update.

#### Mutually exclusive branches (`ELSIF`)

```python
plsql("order", 4, {
    "published": ["status"],
    "_priced":   ["price"],   # leading "_" → ELSIF
})
```

If `status` changes, `orders_upd_published` fires and the `price` branch is skipped, even if `price` also changed.

### Listening from Python

```python
import asyncpg, asyncio, json

async def main():
    conn = await asyncpg.connect(dsn=...)
    await conn.add_listener("my_ads_upd", lambda c, pid, ch, payload: print(ch, json.loads(payload)))
    await asyncio.Future()   # keep the connection open

asyncio.run(main())
```

## Caveats and nuances

- **`NEW.id` is assumed.** The update trigger calls `jsonb_build_array(NEW.id, diff)`, and the delete trigger uses `OLD.id`. Tables without an `id` column require a manual edit of the generated SQL.
- **Channel name pluralisation is naive.** `plsql("my_ad")` yields `my_ads_*` — the library just appends `s`. Pick table names that look reasonable when pluralised this way, or rename the channels after generation.
- **Table name is quoted, channel name is not.** `CREATE TRIGGER` uses `"{table}"` (so reserved words like `order` are safe), but channel names are raw — keep them to lowercase identifiers.
- **`row_to_json` vs `to_jsonb`.** The `NEW` channel uses `row_to_json` (insert payload), the `UPD` diff uses `to_jsonb`. Both serialise PostgreSQL types to JSON, but be aware of how your column types (especially `bytea`, custom enums, ranges) render before relying on the payload format.
- **Payload size limit.** PostgreSQL caps each `NOTIFY` payload at 8000 bytes by default. Wide rows or large text fields can exceed this — prefer narrow update channels (use the `updates` dict) or notify only ids and re-fetch on the consumer side.
- **`CREATE OR REPLACE`.** Both functions and triggers are emitted with `CREATE OR REPLACE`, so re-running the generated script is idempotent.
- **Trigger timing.** All triggers are `AFTER` row triggers and `RETURN NULL` — they don't influence the operation itself.
