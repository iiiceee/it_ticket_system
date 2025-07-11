from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from sqlalchemy import func
import smtplib
from email.mime.text import MIMEText
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
import os

app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 15 * 1024 * 1024  # 15MB
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

from werkzeug.utils import secure_filename
from time import time


app.secret_key = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///tickets.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

@app.route('/')
def hello():
    return render_template('index.html')

# 🧩 Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

class Ticket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(50), default='ใหม่')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

    image1 = db.Column(db.String(200))
    image2 = db.Column(db.String(200))
    image3 = db.Column(db.String(200))

    user = db.relationship('User', backref='tickets')

# 📬 ส่งอีเมลแจ้ง IT
def send_email(subject, content):
    sender = "musashipaint.mfg@gmail.com"
    receiver = "thongchai.buapeng@musashipaint.com"
    msg = MIMEText(content)
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = receiver

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, "leznzyyrivpiyyea") # อย่าลืมใช้ App Password
            server.send_message(msg)
    except Exception as e:
        print("❌ Email send failed:", e)

# หน้าแรก
@app.route('/')
def index():
    return render_template('index.html')

# สมัครสมาชิก
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm = request.form['confirm']

        if password != confirm:
            flash("รหัสผ่านไม่ตรงกัน", "danger")
            return redirect(url_for('register'))

        if User.query.filter_by(username=username).first():
            flash("ชื่อผู้ใช้นี้มีอยู่แล้ว", "warning")
            return redirect(url_for('register'))

        new_user = User(username=username, password=generate_password_hash(password))
        db.session.add(new_user)
        db.session.commit()
        flash("สมัครสมาชิกเรียบร้อยแล้ว", "success")
        return redirect(url_for('login'))

    return render_template('register.html')

# ล็อกอิน
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['is_admin'] = user.is_admin
            flash("เข้าสู่ระบบสำเร็จ", "success")
            return redirect(url_for('index'))
        else:
            flash("ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง", "danger")

    return render_template('login.html')

# ออกจากระบบ
@app.route('/logout')
def logout():
    session.clear()
    flash("ออกจากระบบแล้ว", "info")
    return redirect(url_for('login'))

# เปิด Ticket ใหม่
@app.route('/ticket/new', methods=['GET', 'POST'])
def new_ticket():
    if 'user_id' not in session:
        flash("กรุณาเข้าสู่ระบบก่อน", "warning")
        return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        images = request.files.getlist('images')
        image_paths = []

        # ✅ ตรวจจำนวนรูป
        if len(images) > 3:
            flash("แนบรูปได้ไม่เกิน 3 รูป", "danger")
            return redirect(request.url)

        # ✅ ตรวจขนาดรวม
        total_size = 0
        for img in images:
            if img and allowed_file(img.filename):
                img.seek(0, os.SEEK_END)
                total_size += img.tell()
                img.seek(0)
        if total_size > app.config['MAX_CONTENT_LENGTH']:
            flash("ขนาดรูปทั้งหมดต้องไม่เกิน 15MB", "danger")
            return redirect(request.url)

        # ✅ ตั้งชื่อใหม่ + บันทึก
        timestamp = int(time())
        safe_title = secure_filename(title.replace(" ", "_"))
        for idx, img in enumerate(images[:3]):
            if img and allowed_file(img.filename):
                ext = img.filename.rsplit('.', 1)[-1]
                filename = f"{safe_title}_{idx+1}_{timestamp}.{ext}"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                img.save(filepath)
                image_paths.append(f"uploads/{filename}")  # บันทึก path ที่เรียกจาก static

        ticket = Ticket(
            title=title,
            description=description,
            user_id=session['user_id'],
            image1=image_paths[0] if len(image_paths) > 0 else None,
            image2=image_paths[1] if len(image_paths) > 1 else None,
            image3=image_paths[2] if len(image_paths) > 2 else None
        )
        db.session.add(ticket)
        db.session.commit()

        # 📬 แจ้ง IT ทางอีเมล
        send_email(
            f"📩 Ticket ใหม่จาก {session['username']}",
            f"หัวข้อ: {title}\n\nรายละเอียด:\n{description}"
        )

        flash("เปิด Ticket สำเร็จแล้ว", "success")
        return redirect(url_for('index'))

    return render_template('new_ticket.html')



# ดูตั๋วของฉัน
@app.route('/my_tickets')
def my_tickets():
    if 'user_id' not in session:
        flash("กรุณาเข้าสู่ระบบก่อน", "warning")
        return redirect(url_for('login'))

    tickets = Ticket.query.filter_by(user_id=session['user_id']).order_by(Ticket.created_at.desc()).all()
    return render_template('my_tickets.html', tickets=tickets)

# แสดง / แก้ไข / ลบ Ticket
@app.route('/ticket/<int:ticket_id>', methods=['GET', 'POST'])
def ticket_detail(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)

    if session.get('user_id') != ticket.user_id and not session.get('is_admin'):
        flash("คุณไม่มีสิทธิ์เข้าถึง Ticket นี้", "danger")
        return redirect(url_for('index'))


    if request.method == 'POST':
        if 'update' in request.form:
            ticket.title = request.form['title']
            ticket.description = request.form['description']
            ticket.updated_at = datetime.utcnow()
            db.session.commit()
            flash("อัปเดต Ticket สำเร็จ", "success")
        elif 'delete' in request.form:
            db.session.delete(ticket)
            db.session.commit()
            flash("ลบ Ticket เรียบร้อย", "info")
            return redirect(url_for('my_tickets'))
        elif 'add_comment' in request.form:
            content = request.form['comment']
            comment = Comment(content=content, user_id=session['user_id'], ticket_id=ticket_id)
            db.session.add(comment)
            db.session.commit()
            flash("ส่งคอมเมนต์เรียบร้อย", "success")

    comments = Comment.query.filter_by(ticket_id=ticket_id).order_by(Comment.created_at.desc()).all()
    return render_template('ticket_detail.html', ticket=ticket, comments=comments)


# แดชบอร์ดของทีม IT
@app.route('/admin/dashboard')
def dashboard():
    if not session.get('is_admin'):
        flash("สำหรับผู้ดูแลระบบเท่านั้น", "danger")
        return redirect(url_for('index'))

    from sqlalchemy.orm import joinedload

    # ✅ รับค่าหน้าจาก query string เช่น /admin/dashboard?page=2
    page = request.args.get('page', 1, type=int)
    per_page = 10  # ปรับตามความเหมาะสม

    # ✅ โหลด tickets แบบแบ่งหน้า (pagination) พร้อม user
    tickets = Ticket.query.options(joinedload(Ticket.user)) \
        .order_by(Ticket.created_at.desc()) \
        .paginate(page=page, per_page=per_page, error_out=False)  # <— ต้องใส่ error_out=False ด้วย

    # ✅ โหลด comments แยกตาม ticket ในหน้านี้
    comments_by_ticket = {
        ticket.id: Comment.query.options(joinedload(Comment.user))
            .filter_by(ticket_id=ticket.id)
            .order_by(Comment.created_at.asc())
            .all()
        for ticket in tickets.items  # <— ต้องเป็น .items
    }

    # ✅ คำนวณสถิติรวม (optional)
    weekly = db.session.query(func.count()).filter(
        func.strftime('%W', Ticket.created_at) == func.strftime('%W', func.current_date())
    ).scalar()
    monthly = db.session.query(func.count()).filter(
        func.strftime('%m', Ticket.created_at) == func.strftime('%m', func.current_date())
    ).scalar()
    yearly = db.session.query(func.count()).filter(
        func.strftime('%Y', Ticket.created_at) == func.strftime('%Y', func.current_date())
    ).scalar()
    pending = Ticket.query.filter_by(status='ใหม่').count()
    processing = Ticket.query.filter_by(status='รับงานแล้ว').count()

    # Pagination helper
    start_page = max(1, page - 2)
    end_page = min(tickets.pages, page + 2)

    from collections import OrderedDict, defaultdict

    # สร้าง dict เก็บจำนวน ticket ต่อเดือน
    monthly_status_counts = defaultdict(lambda: {'ใหม่': 0, 'รับงานแล้ว': 0, 'เสร็จแล้ว': 0})

    tickets_in_year = Ticket.query.filter(
        func.strftime('%Y', Ticket.created_at) == str(datetime.utcnow().year)
    ).all()

    for t in tickets_in_year:
        month = t.created_at.strftime('%m')
        monthly_status_counts[month][t.status] += 1

    months = [datetime(2025, int(m), 1).strftime('%b') for m in range(1, 13)]
    new_counts = [monthly_status_counts[str(m).zfill(2)]['ใหม่'] for m in range(1, 13)]
    processing_counts = [monthly_status_counts[str(m).zfill(2)]['รับงานแล้ว'] for m in range(1, 13)]
    done_counts = [monthly_status_counts[str(m).zfill(2)]['เสร็จแล้ว'] for m in range(1, 13)]

    return render_template("dashboard.html",
        tickets=tickets,
        comments_by_ticket=comments_by_ticket,
        page=page,
        start_page=start_page,
        end_page=end_page,
        weekly=weekly,
        monthly=monthly,
        yearly=yearly,
        pending=pending,
        processing=processing,
        months=months,
        new_counts=new_counts,
        processing_counts=processing_counts,
        done_counts=done_counts
    )





# อัปเดตสถานะตั๋ว
@app.route('/admin/update_status/<int:ticket_id>', methods=['POST'])
def update_status(ticket_id):
    if not session.get('is_admin'):
        flash("สำหรับผู้ดูแลระบบเท่านั้น", "danger")
        return redirect(url_for('index'))

    ticket = Ticket.query.get_or_404(ticket_id)
    ticket.status = request.form['status']
    ticket.updated_at = datetime.utcnow()
    db.session.commit()

    comment_text = request.form.get('comment')
    if comment_text:
        comment = Comment(content=comment_text, user_id=session['user_id'], ticket_id=ticket_id)
        db.session.add(comment)
        db.session.commit()

    flash("อัปเดตสถานะเรียบร้อย", "success")
    return redirect(url_for('dashboard'))


class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    ticket_id = db.Column(db.Integer, db.ForeignKey('ticket.id'))
    user = db.relationship("User", backref="comments")

# โหลด Excel
from openpyxl import Workbook
from openpyxl.drawing.image import Image as ExcelImage
from flask import send_file
import tempfile

@app.route('/admin/report/excel')
def download_excel():
    if not session.get('is_admin'):
        flash("สำหรับผู้ดูแลระบบเท่านั้น", "danger")
        return redirect(url_for('index'))

    tickets = Ticket.query.order_by(Ticket.created_at.desc()).all()

    wb = Workbook()
    ws = wb.active
    ws.title = "รายงาน Ticket"

    # 📝 หัวตาราง
    headers = ["หัวข้อ", "รายละเอียด", "สถานะ", "วันที่สร้าง", "อัปเดตล่าสุด"]
    ws.append(headers)

    for ticket in tickets:
        ws.append([
            ticket.title,
            ticket.description,
            ticket.status,
            ticket.created_at.strftime('%Y-%m-%d'),
            ticket.updated_at.strftime('%Y-%m-%d')
        ])

    # 🎨 จัดความกว้างคอลัมน์ให้อ่านง่าย
    for col in ws.columns:
        max_length = max(len(str(cell.value)) for cell in col)
        ws.column_dimensions[col[0].column_letter].width = max(15, max_length + 2)

    # 📁 บันทึกลงไฟล์ชั่วคราว
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx')
    wb.save(tmp.name)
    tmp.close()

    return send_file(tmp.name, as_attachment=True, download_name="report.xlsx")



# รันเซิร์ฟเวอร์
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)

    
