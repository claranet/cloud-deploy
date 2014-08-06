from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from models import CDApp, Configuration, Task, db

engine = create_engine('sqlite:///ghost.db', echo=True)
db.metadata.create_all(engine)
