"""Services / email service."""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import parseaddr

from flask import current_app as app
from itsdangerous import URLSafeTimedSerializer


def get_reset_serializer():
    return URLSafeTimedSerializer(app.config["SECRET_KEY"])


def send_password_reset_email(to_email, reset_url, verification_code):
    """Gửi mã xác thực và liên kết đặt lại mật khẩu qua SMTP."""
    mail_username = app.config.get("MAIL_USERNAME")
    mail_password = app.config.get("MAIL_PASSWORD")
    configured_sender = app.config.get("MAIL_DEFAULT_SENDER", "").strip()
    configured_sender_email = parseaddr(configured_sender)[1]
    sender_email = configured_sender_email or mail_username
    sender = configured_sender if configured_sender_email else f"Lego Flower <{sender_email}>"

    html_content = f"""
    <div style="font-family: Arial, sans-serif; max-width: 580px; margin: 0 auto; padding: 28px; border: 1.5px solid #C9A227; border-radius: 16px; background: #ffffff;">
        <div style="text-align: center; margin-bottom: 24px;">
            <h2 style="color: #21243D; margin: 0 0 6px 0; font-size: 24px;">Lego Flower</h2>
            <p style="color: #6c757d; font-size: 14px; margin: 0;">Khôi phục mật khẩu tài khoản</p>
        </div>
        <p style="color: #333333; font-size: 15px; line-height: 1.6;">Xin chào,</p>
        <p style="color: #333333; font-size: 15px; line-height: 1.6;">Chúng tôi nhận được yêu cầu đặt lại mật khẩu cho tài khoản Lego Flower liên kết với địa chỉ email <strong>{to_email}</strong>.</p>
        <p style="color: #333333; font-size: 15px; line-height: 1.6;">Mã xác thực của bạn là:</p>
        <div style="text-align: center; margin: 20px 0; font-size: 30px; font-weight: bold; letter-spacing: 8px; color: #21243D;">{verification_code}</div>
        <p style="color: #333333; font-size: 15px; line-height: 1.6;">Nhập mã này tại trang đặt lại mật khẩu. Mã và liên kết có hiệu lực trong vòng 30 phút.</p>
        <div style="text-align: center; margin: 30px 0;">
            <a href="{reset_url}" style="display: inline-block; background: #C9A227; color: #ffffff; text-decoration: none; padding: 12px 30px; border-radius: 10px; font-weight: bold; font-size: 15px; letter-spacing: 0.3px;">Đặt lại mật khẩu</a>
        </div>
        <p style="color: #6c757d; font-size: 13px; line-height: 1.6;">Nếu nút trên không hoạt động, bạn có thể sao chép liên kết sau và dán vào thanh địa chỉ trình duyệt:<br>
            <a href="{reset_url}" style="color: #C9A227; word-break: break-all;">{reset_url}</a>
        </p>
        <p style="color: #8c857b; font-size: 13px; line-height: 1.5; margin-top: 24px;">
            <em>Nếu bạn không yêu cầu đặt lại mật khẩu, vui lòng bỏ qua email này. Mật khẩu của bạn vẫn an toàn.</em>
        </p>
        <hr style="border: none; border-top: 1px solid #eeeeee; margin: 24px 0 16px 0;">
        <p style="color: #aaaaaa; font-size: 12px; text-align: center; margin: 0;">Lego Flower Shop &bull; Shop hoa Lego nghệ thuật cao cấp</p>
    </div>
    """

    if not mail_username or not mail_password:
        return False, "Chưa cấu hình MAIL_USERNAME và MAIL_PASSWORD."

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "[Lego Flower] Đặt lại mật khẩu tài khoản"
        msg["From"] = sender
        msg["To"] = to_email
        msg.attach(MIMEText(html_content, "html", "utf-8"))

        with smtplib.SMTP(
            app.config.get("MAIL_SERVER"), app.config.get("MAIL_PORT"), timeout=10
        ) as server:
            server.ehlo()
            if app.config.get("MAIL_USE_TLS"):
                server.starttls()
                server.ehlo()
            server.login(mail_username, mail_password)
            server.sendmail(sender_email, [to_email], msg.as_string())
        return True, "sent"
    except Exception as ex:
        print(f"[ERROR GỬI EMAIL] {ex}")
        return False, str(ex)
