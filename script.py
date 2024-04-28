from flask import Flask, request, render_template, redirect, url_for, session, jsonify
from flask_session import Session
import os
import fitz  # PyMuPDF
from collections import defaultdict
import json
import re
import pandas as pd
import uuid
import requests
from io import BytesIO
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from dotenv import load_dotenv
from flask_migrate import Migrate
from sqlalchemy.dialects.postgresql import UUID as pgUUID
from uuid import uuid4
from uuid import UUID
from datetime import timedelta
import logging
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SESSION_TYPE'] = 'sqlalchemy'
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)
app.config['SESSION_USE_SIGNER'] = True
app.config['SESSION_COOKIE_NAME'] = 'your_session_cookie'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SECURE'] = True  # HTTPS 환경에서만 사용할 경우
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
app.config['SESSION_SQLALCHEMY'] = db  # 세션에 사용할 SQLAlchemy 인스턴스 지정
migrate = Migrate(app, db)
Session(app)  # Flask-Session 구성

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf', 'xlsx'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)  # 사용자 이름 필드
    reviews = db.relationship('ReviewSession', backref='user', lazy=True)

class ReviewSession(db.Model):
    id = db.Column(pgUUID, primary_key=True, default=uuid.uuid4)
    ebook_title = db.Column(db.String(150), nullable=False)
    review_text = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    review_stage = db.Column(db.String(50), nullable=False, default='not_reviewed')
    levels = db.Column(db.JSON)  # JSON 타입으로 레벨 데이터 저장
    word_sentences = db.Column(db.JSON)  # JSON 타입으로 단어 문장 데이터 저장
    
    

    def __repr__(self):
        return f'<ReviewSession {self.ebook_title} - Stage: {self.review_stage}>'

def save_review_data(session_id, levels, word_sentences):
    session_data = ReviewSession.query.filter_by(id=session_id).first()
    if session_data:
        session_data.levels = levels
        session_data.word_sentences = word_sentences
        db.session.commit()

def load_review_data(session_id):
    session_data = ReviewSession.query.filter_by(id=session_id).first()
    if session_data:
        return session_data.levels, session_data.word_sentences
    else:
        return None, None




    
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def find_word_sentences(pdf_path, words):
    """Find sentences containing any of the specified words in a PDF."""
    doc = fitz.open(pdf_path)  # PDF 파일 열기
    word_sentences = defaultdict(list)  # 각 단어에 대한 문장들을 저장할 딕셔너리
    for page in doc:  # PDF 내 각 페이지에 대해 반복
        text = page.get_text("text")  # 페이지의 텍스트 추출
        sentences = text.split('. ')  # 문장 단위로 분리
        for sentence in sentences:  # 각 문장에 대해 반복
            for word in words:  # 주어진 단어 리스트에 대해 반복
                if word.lower() in sentence.lower():  # 문장 내에 단어가 포함되어 있는지 검사 (소문자로 변환하여 검사)
                    start_index = max(sentence.lower().find(word) - 30, 0)  # 문장 내에서 단어 시작 위치 찾기
                    end_index = min(sentence.lower().find(word) + len(word) + 30, len(sentence))  # 단어 끝 위치 설정
                    snippet = sentence[start_index:end_index]  # 단어 주변의 텍스트 스니펫 추출
                    word_sentences[word].append(snippet)  # 결과 딕셔너리에 추가
    return dict(word_sentences)  # 완성된 딕셔너리 반환



def read_excel_file(file_path):
    """Read Excel file and categorize words by levels."""
    df = pd.read_excel(file_path, usecols=['Word', 'Level', 'Meaning'])
    levels = defaultdict(list)
    for _, row in df.iterrows():
        levels[row['Level']].append({'word': row['Word'], 'meaning': row['Meaning']})
    return dict(levels)



@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        user_name = request.form.get('username')
        wordlist_file = request.files.get('wordlist')
        ebook_file = request.files.get('ebook')

        if not user_name or not wordlist_file or not ebook_file:
            return render_template('upload.html', message='Please enter your name and upload files.')

        new_user = User(name=user_name)
        db.session.add(new_user)
        db.session.commit()

        unique_id = uuid.uuid4().hex
        wordlist_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{unique_id}_wordlist.xlsx")
        ebook_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{unique_id}_ebook.pdf")
        wordlist_file.save(wordlist_path)
        ebook_file.save(ebook_path)

        levels = read_excel_file(wordlist_path)
        all_words = [word['word'] for level_words in levels.values() for word in level_words]
        word_sentences = find_word_sentences(ebook_path, all_words)

        # 새로운 리뷰 세션 생성 및 저장
        new_session = ReviewSession(
            id=unique_id,
            ebook_title=ebook_file.filename,
            user_id=new_user.id,
            review_stage='not_reviewed',
            levels=levels,  # 데이터베이스에 레벨 데이터 저장
            word_sentences=word_sentences  # 데이터베이스에 단어 문장 데이터 저장
        )
        db.session.add(new_session)
        db.session.commit()

        return redirect(url_for('show_results', unique_id=unique_id))

    reviewed_books = get_reviewed_books()
    return render_template('upload.html', reviewed_books=reviewed_books)


def get_reviewed_books():
    # DB에서 1차 검토 완료된 전자책 목록을 가져오는 로직
    return ReviewSession.query.filter_by(review_stage='first_review_complete').all()



@app.route('/create_user', methods=['POST'])
def create_user():
    name = request.form['name']  # 사용자 이름을 폼 데이터에서 받아옴
    if name:
        new_user = User(name=name)  # User 모델 인스턴스 생성
        db.session.add(new_user)  # 세션에 추가
        db.session.commit()  # 데이터베이스에 커밋
        return jsonify({"message": "User created successfully", "user": {"id": new_user.id, "name": new_user.name}}), 201
    else:
        return jsonify({"error": "Name is required"}), 400

def is_valid_uuid(uuid_to_check):
    try:
        UUID(uuid_to_check, version=4)
        return True
    except ValueError:
        return False

logging.basicConfig(level=logging.DEBUG)
    
@app.route('/show_results', methods=['GET'])
def show_results():
    unique_id = request.args.get('unique_id')
    
    # UUID 검증
    if not is_valid_uuid(unique_id):
        return render_template('error.html', message="Invalid UUID format."), 400

    # UUID 형식 변경 (필요한 경우)
    try:
        if len(unique_id) == 32:  # UUID가 하이픈 없이 제공될 경우
            formatted_uuid = f"{unique_id[:8]}-{unique_id[8:12]}-{unique_id[12:16]}-{unique_id[16:20]}-{unique_id[20:]}"
            unique_id = formatted_uuid
        review_session = ReviewSession.query.filter_by(id=unique_id).first()
    except ValueError:
        return render_template('error.html', message="Error converting UUID."), 400

    if not review_session:
        return render_template('error.html', message="No valid session found for the given ID."), 404

    # 세션 대신 데이터베이스에서 직접 데이터 로드
    levels = review_session.levels
    word_sentences = review_session.word_sentences
    if levels is None or word_sentences is None:
        return render_template('error.html', message="Data not properly loaded."), 400

    return render_template('show_results.html', levels=levels, word_sentences=word_sentences, unique_id=unique_id)


@app.route('/some_route')
def some_function():
    unique_id = request.args.get('unique_id', '')
    levels = session.get(f'levels_{unique_id}', None)
    word_sentences = session.get(f'word_sentences_{unique_id}', None)
    
    logging.debug(f"Loaded levels for {unique_id}: {levels}")
    logging.debug(f"Loaded word_sentences for {unique_id}: {word_sentences}")

    if levels is None or word_sentences is None:
        logging.error(f"Session data not properly loaded for unique_id {unique_id}")
        return "Data not loaded properly", 400
    
    return jsonify(levels=levels, word_sentences=word_sentences)

@app.route('/test_session')
def test_session():
    session['test'] = 'This is a test'
    test_value = session.get('test', 'No session found')
    return f"Session value: {test_value}"

@app.route('/another_route', methods=['GET'])
def another_function():
    unique_id = 'some_unique_id'
    levels, word_sentences = load_review_data(unique_id)
    if levels is None or word_sentences is None:
        return render_template('error.html', message="Session data not loaded properly."), 400
    return render_template('data_display.html', levels=levels, word_sentences=word_sentences)



@app.route('/update_word_count', methods=['POST'])
def update_word_count():
    data = request.get_json()
    word = data['word']
    count = data['count']
    unique_id = data['unique_id']  # unique_id를 요청 데이터에서 가져옵니다.
    final_word_counts_key = f'final_word_counts_{unique_id}'  # unique_id를 포함한 세션 키
    final_word_counts = session.get(final_word_counts_key, {})
    final_word_counts[word] = count
    session[final_word_counts_key] = final_word_counts
    return jsonify({"status": "success", "word": word, "count": count})

@app.route('/complete_review/<unique_id>', methods=['POST'])
def complete_review(unique_id):
    if not is_valid_uuid(unique_id):
        return jsonify({'status': 'error', 'message': 'Invalid UUID format'}), 400

    review_session = ReviewSession.query.filter_by(id=unique_id).first()
    if not review_session:
        logging.error(f"Review session not found for ID: {unique_id}")
        return jsonify({'status': 'error', 'message': 'Review session not found'}), 404

    next_stage = {
        'not_reviewed': 'first_review_complete',
        'first_review_complete': 'second_review_complete',
        'second_review_complete': 'review_complete'
    }
    current_stage = review_session.review_stage
    review_session.review_stage = next_stage.get(current_stage, current_stage)
    db.session.commit()
    logging.info(f"Review session updated to {review_session.review_stage} for ID: {unique_id}")
    return jsonify({'status': 'success', 'message': f'Review updated to {review_session.review_stage}'})

def reload_session_data(unique_id):
    """ 데이터베이스에서 세션 데이터를 새로 로드하고 세션에 저장합니다. """
    session_data = ReviewSession.query.filter_by(id=unique_id).first()
    if session_data:
        # 예제에서는 session_data가 levels와 word_sentences를 가정하고 있습니다.
        # 실제로는 해당 정보를 적절히 로드하고 저장하는 로직이 필요합니다.
        # 예를 들어, ReviewSession 모델이 관련 정보를 포함하고 있다면 다음과 같이 접근할 수 있습니다.
        # session[f'levels_{unique_id}'] = session_data.get_levels()  # get_levels는 가정된 메서드입니다.
        # session[f'word_sentences_{unique_id}'] = session_data.get_word_sentences()  # get_word_sentences는 가정된 메서드입니다.
        
        # 현재 예제로는 다음과 같이 가정하고 수정할 수 있습니다.
        # 이 부분은 실제 데이터 모델과 구조에 맞게 조정해야 합니다.
        if hasattr(session_data, 'get_levels') and callable(session_data.get_levels):
            session[f'levels_{unique_id}'] = session_data.get_levels()
        if hasattr(session_data, 'get_word_sentences') and callable(session_data.get_word_sentences):
            session[f'word_sentences_{unique_id}'] = session_data.get_word_sentences()
    else:
        # 세션 데이터 로드 실패
        logging.error("Failed to reload session data for unique_id: {}".format(unique_id))



@app.route('/start_second_review/<unique_id>', methods=['GET'])
def start_second_review(unique_id):
    # UUID 검증
    if not is_valid_uuid(unique_id):
        logging.error("Invalid UUID format")
        return "Error: Invalid unique ID.", 400

    # 데이터베이스에서 리뷰 세션 조회
    review_session = ReviewSession.query.filter_by(id=unique_id).first()
    if not review_session:
        logging.error("No valid session found for the given ID")
        return render_template('error.html', message="No valid session found for the given ID."), 404

    # 데이터베이스에서 직접 데이터 로드
    levels = review_session.levels
    word_sentences = review_session.word_sentences
    if levels is None or word_sentences is None:
        logging.error(f"Session data not properly loaded for unique_id {unique_id}")
        return render_template('error.html', message="Session data not properly loaded. Please try again."), 400

    # 리뷰 단계 업데이트 및 데이터베이스 커밋
    review_session.review_stage = 'second_review_started'
    db.session.commit()
    logging.info(f"Review session updated to second_review_started for ID: {unique_id}")
    return redirect(url_for('show_results', unique_id=unique_id))








@app.route('/some_route')
def some_route():
    session.permanent = True  # 세션 만료를 PERMANENT_SESSION_LIFETIME 설정에 따라 결정
    # 세션 데이터 작업
    return 'Something'



@app.route('/final_results')
def final_results():
    unique_id = request.args.get('unique_id')
    
    # 데이터베이스에서 리뷰 세션을 직접 조회
    review_session = ReviewSession.query.filter_by(id=unique_id).first()
    final_word_counts = session.get(f'final_word_counts_{unique_id}')
    
    # 데이터베이스 조회 결과를 검증
    if not review_session:
        return render_template('error.html', message="No valid session found."), 404
    
    # levels와 word_sentences 데이터 로드
    levels = review_session.levels
    word_sentences = review_session.word_sentences
    
    # 로드된 데이터 검증
    if not levels or not word_sentences:
        return render_template('error.html', message="Data not loaded properly. Please try again."), 400


    # 각 레벨별 단어 개수 계산
    count_by_level = {}
    for level, words in levels.items():
        count_by_level[level] = sum(final_word_counts.get(word['word'], 0) for word in words)

    sum_counts_by_level = {}
    for level, words in levels.items():
        sum_counts_by_level[level] = sum(1 for word in words if final_word_counts.get(word['word'], 0) > 0)

    return render_template('final_results.html', count_by_level=count_by_level, sum_counts_by_level=sum_counts_by_level)



@app.route('/compare_results', methods=['GET'])
def compare_results():
    session_id1 = request.args.get('session_id1')
    session_id2 = request.args.get('session_id2')
    results1 = session.get(f'word_sentences_{session_id1}', {})
    results2 = session.get(f'word_sentences_{session_id2}', {})

    # 여기서 결과 비교 로직을 구현할 수 있습니다.
    # 예를 들어, 두 결과 집합에서 단어와 문장 수를 비교하여 차이점을 도출
    comparison_result = {}  # 결과 비교 로직 구현 필요
    for word in set(results1.keys()).union(results2.keys()):
        count1 = len(results1.get(word, []))
        count2 = len(results2.get(word, []))
        if count1 != count2:
            comparison_result[word] = (count1, count2)

    return render_template('compare_results.html', comparison=comparison_result)





@app.route('/save_word_counts', methods=['POST'])
def save_word_counts():
    data = request.json
    session['word_counts'] = data
    return jsonify({"status": "success"})



if __name__ == '__main__':
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    app.run(debug=True)