"""Chat database models. Existing table names are preserved."""

from datetime import datetime

from app.extensions import db


class ChatMessage(db.Model):
    """Tin nhắn chat giữa khách hàng và Admin / Shop."""

    __tablename__ = "chat_messages"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(64), nullable=False, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=True, index=True)
    sender_type = db.Column(db.String(20), nullable=False)  # 'customer' hoặc 'admin'
    sender_name = db.Column(db.String(100), nullable=False)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    is_read = db.Column(db.Boolean, default=False, index=True)

    customer = db.relationship("Customer", backref=db.backref("chat_messages", lazy=True))

    __table_args__ = (
        db.Index("idx_chat_messages_session_id_id", "session_id", "id"),
        db.Index("idx_chat_messages_unread_badge", "sender_type", "is_read"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "session_id": self.session_id,
            "customer_id": self.customer_id,
            "sender_type": self.sender_type,
            "sender_name": self.sender_name,
            "message": self.message,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "time_str": self.created_at.strftime("%H:%M"),
            "is_read": self.is_read,
        }

    def __repr__(self):
        return f"<ChatMessage {self.id} from {self.sender_type} ({self.sender_name})>"
