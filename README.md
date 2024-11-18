[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://github.com/pre-commit/pre-commit)

# Postgres channels
Generates PL/pgSQL script creating LISTEN/NOTIFY channels from just table name and dict of update triggers with fields sets.

Function `plsql` takes one requiered `:str` arg - table_name, and generates PL/pgSQL script for creating 3 channels for 3 type events:

### Examples
###### On table: Fire `tables_new`: on create entity in `table`, `tables_del`: on delete entity from `table`, and `tables_upd`: on update any `table.field`:
```python
plsql('table')
```

And second optional `:dict` arg - dict of `list/tuples` of specified fields for triggering update event(s):
###### Set exactly field for triggering event: Fire `tables_upd_event1`: on update `table.field1`:
```python
plsql('table', 7, {'event1': ['field1']})
```

###### AND/OR conditions: Fire `tables_upd_event1`: on update `field1 AND field2`, and `tables_upd_event2`: on update `field2 OR field3`:
```python
{'event1': ('field1','field2'), 5, '_event2': ['field2', 'field3']}
```