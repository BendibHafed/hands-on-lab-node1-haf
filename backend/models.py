from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class FirstNodeState(db.Model):
    __tablename__ = "node1_state"
    
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.String(50))
    ts = db.Column(db.Float, nullable=True)

    def __repr__(self):
        return f"<First Node State {self.key}={self.value}>" 