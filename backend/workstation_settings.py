"""Workstation model preferences, stored inside the account-encrypted database."""
import json
import logging


def initialize(app, model, offline_override=None):
    if app.state.settings_loaded or app.state.database.locked:
        return
    with app.state.database.connect() as connection:
        connection.execute('CREATE TABLE IF NOT EXISTS workstation_settings (id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL)')
        row=connection.execute('SELECT payload FROM workstation_settings WHERE id=1').fetchone()
    if row:
        try:
            saved=model.model_validate(json.loads(row['payload']))
            if offline_override is not None:
                saved.offline_mode=offline_override
                if offline_override:
                    saved.qa_provider='ollama';saved.qa_url=app.state.qa_url
            for key,value in saved.model_dump().items():setattr(app.state,key,value)
        except (ValueError,TypeError):
            logging.getLogger(__name__).warning('Saved workstation settings could not be restored.')
    app.state.settings_loaded=True


def save(app, model, updates):
    values={key:getattr(app.state,key) for key in model.model_fields}
    values.update(updates)
    saved=model.model_validate(values)
    with app.state.database.connect() as connection:
        connection.execute('INSERT INTO workstation_settings (id,payload) VALUES (1,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload',
                           (saved.model_dump_json(),))
    for key,value in saved.model_dump().items():setattr(app.state,key,value)
