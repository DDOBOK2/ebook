from flask import Flask, request, render_template, redirect, url_for, session, jsonify, current_app
from flask_session import Session
from dotenv import load_dotenv
load_dotenv()
import os
import tempfile
from werkzeug.utils import secure_filename
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
from flask_migrate import Migrate
from sqlalchemy.dialects.postgresql import UUID as pgUUID
from uuid import uuid4
from uuid import UUID
from datetime import timedelta
import logging
from sqlalchemy.exc import SQLAlchemyError
from flask import send_file
from werkzeug.datastructures import MultiDict
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders


app = Flask(__name__)
from flask_mail import Mail, Message
mail = Mail(app)
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'pbh1527@naver.com'
app.config['MAIL_PASSWORD'] = 'leejunyoung18@'
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SESSION_TYPE'] = 'sqlalchemy'
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)
app.config['SESSION_USE_SIGNER'] = True
app.config['SESSION_COOKIE_NAME'] = 'your_session_cookie'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SECURE'] = True  # HTTPS 환경에서만 사용할 경우
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL').replace("postgres://", "postgresql://", 1)
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
    final_word_counts = db.Column(db.JSON)  # 최종 단어 카운트 저장
    initial_word_counts = db.Column(db.JSON)  # 초기 단어 카운트 저장
    deleted_sentences = db.Column(db.JSON, default=dict)
    word_review_status = db.Column(db.JSON, default=dict)  # 단어별 검토 상태 저장 

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

def find_word_sentences(pdf_path, words, session_id):
    """Find sentences containing any of the specified words in a PDF."""
    doc = fitz.open(pdf_path)  # PDF 파일 열기
    word_sentences = defaultdict(list)  # 각 단어에 대한 문장들을 저장할 딕셔너리
    word_counts = defaultdict(int)  # 총 발생 횟수를 저장하기 위한 사전

    for page in doc:  # PDF 내 각 페이지에 대해 반복
        text = page.get_text("text")  # 페이지의 텍스트 추출
        sentences = text.split('. ')  # 문장 단위로 분리
        for sentence in sentences:  # 각 문장에 대해 반복
            for word in words:  # 주어진 단어 리스트에 대해 반복
                if word.lower() in sentence.lower():  # 문장 내에 단어가 포함되어 있는지 검사 (소문자로 변환하여 검사)
                    start_index = max(sentence.lower().find(word) - 30, 0)  # 문장 내에서 단어 시작 위치 찾기
                    end_index = min(sentence.lower().find(word) + len(word) + 30, len(sentence))  # 단어 끝 위치 설정
                    snippet = sentence[start_index:end_index]  # 단어 주변의 텍스트 스니펫 추출
                    # word_sentences에 값을 추가하기 전에 로그로 기록
                    if not isinstance(word_sentences[word], list):  # 여기서 데이터 타입 검사 추가
                        logging.error(f"Attempting to store invalid data type for word '{word}': {type(word_sentences[word])}")
                    else:
                        word_sentences[word].append(snippet)  # 결과 딕셔너리에 추가
                    word_counts[word] += 1  # 단어 발생 횟수 업데이트
    word_sentences = dict(word_sentences)                  
    print("Word Sentences:", word_sentences)
    update_word_counts_in_db(session_id, dict(word_counts))  # Update the database with word counts
    return word_sentences, dict(word_counts)  # 단어 문장과 발생 횟수 모두 반환

def update_word_counts_in_db(session_id, word_counts):
    session = ReviewSession.query.filter_by(id=session_id).first()
    if session:
        session.final_word_counts = word_counts
        db.session.commit()
        print(f"Updated word counts for session {session_id}: {word_counts}")  # 로그 추가
def read_excel_file(file_path):
    """Read Excel file and categorize words by levels."""
    df = pd.read_excel(file_path, usecols=['Word', 'Level', 'Meaning', 'Kanji'])
    levels = defaultdict(list)
    for _, row in df.iterrows():
        levels[row['Level']].append({'word': row['Word'], 'meaning': row['Meaning'], 'kanji': row['Kanji']})
    return dict(levels)

def compare_deletions(details):
    deleted_by_first = set(map(int, details.get("deleted_by_first_reviewer", [])))
    deleted_by_second = set(map(int, details.get("deleted_by_second_reviewer", [])))
    common_deletions = sorted(deleted_by_first.intersection(deleted_by_second))
    differences = sorted(deleted_by_first.symmetric_difference(deleted_by_second))
    return common_deletions, differences




@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        # POST 요청 처리: 파일 업로드 및 사용자 정보 저장
        user_name = request.form.get('username')
        ebook_file = request.files.get('ebook')

        if not user_name or not ebook_file:
            return render_template('upload.html', message='Please enter your name and upload the ebook file.')

        new_user = User(name=user_name)
        db.session.add(new_user)
        db.session.commit()

        unique_id = uuid.uuid4().hex
        # 임시 디렉토리 생성
        with tempfile.TemporaryDirectory() as temp_dir:
            # 안전한 파일 이름 생성
            ebook_filename = secure_filename(ebook_file.filename)
            ebook_path = os.path.join(temp_dir, ebook_filename)
            # 임시 경로에 파일 저장
            wordlist_path = 'resources/wordlist.xlsx'
            ebook_file.save(ebook_path)


            levels = read_excel_file(wordlist_path)
            all_words = [word['word'] for level_words in levels.values() for word in level_words]
            word_sentences_dict, word_counts_dict = find_word_sentences(ebook_path, all_words, unique_id)

            new_session = ReviewSession(
                id=unique_id,
                ebook_title=ebook_file.filename,
                user_id=new_user.id,
                review_stage='not_reviewed',
                levels=levels,
                word_sentences=word_sentences_dict,
                final_word_counts=word_counts_dict
            )
            db.session.add(new_session)
            db.session.commit()

        return redirect(url_for('show_results', unique_id=unique_id))
    
    else:
        # GET 요청 처리: 검색 기능 및 목록 표시
        search_query = request.args.get('search', '')  # 검색어 쿼리
        reviewed_books = get_reviewed_books(search_query)
        return render_template('upload.html', reviewed_books=reviewed_books)


def get_reviewed_books(search_query=''):
    query = ReviewSession.query.filter(
        ReviewSession.review_stage.in_(['not_reviewed', 'first_review_complete', 'second_review_started', 'second_review_complete', 'third_review_started'])
    )
    if search_query:
        query = query.filter(ReviewSession.ebook_title.ilike(f'%{search_query}%'))
    return query.order_by(ReviewSession.created_at.desc()).all()

@app.route('/save_review_status', methods=['POST'])
def save_review_status():
    data = request.get_json()
    unique_id = data['unique_id']
    review_status = data['review_status']

    review_session = ReviewSession.query.filter_by(id=unique_id).first()
    if review_session:
        review_session.word_review_status = review_status
        db.session.commit()
        return jsonify({'status': 'success'}), 200
    return jsonify({'status': 'error', 'message': 'Review session not found'}), 404

@app.route('/load_review_status/<unique_id>', methods=['GET'])
def load_review_status(unique_id):
    review_session = ReviewSession.query.filter_by(id=unique_id).first()
    if review_session:
        return jsonify({'status': 'success', 'review_status': review_session.word_review_status}), 200
    return jsonify({'status': 'error', 'message': 'Review session not found'}), 404


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
    if len(unique_id) == 32:  # UUID가 하이픈 없이 제공될 경우
        formatted_uuid = f"{unique_id[:8]}-{unique_id[8:12]}-{unique_id[12:16]}-{unique_id[16:20]}-{unique_id[20:]}"
        unique_id = formatted_uuid

    review_session = ReviewSession.query.filter_by(id=unique_id).first()
    if review_session:
        # JSON 필드인 'deleted_sentences'를 처리하는 로직 수정
        if isinstance(review_session.deleted_sentences, str):
            try:
                deleted_sentences = json.loads(review_session.deleted_sentences)
            except json.JSONDecodeError as e:
                logging.error(f"JSON decoding error: {e}")
                return render_template('error.html', message="Error decoding deleted sentences."), 400
        elif isinstance(review_session.deleted_sentences, dict):
            deleted_sentences = review_session.deleted_sentences
        else:
            deleted_sentences = {}  # 기본값 설정
        logging.debug(f"Loaded deleted_sentences: {review_session.deleted_sentences}")
        # 추가적으로 'levels' 필드가 필요하다면 여기서 처리
        levels = review_session.levels if review_session.levels else {}
        

    if not review_session:
        logging.error(f"No valid session found for ID: {unique_id}")
        return render_template('error.html', message="No valid session found for the given ID."), 404
    levels = review_session.levels
    try:
        word_sentences = review_session.word_sentences

        # 데이터 로드 후 타입 확인 및 변환
        if isinstance(word_sentences, list) and len(word_sentences) > 0:
            # 리스트 형태인 경우 첫 번째 요소 사용 (이 예제에서는 첫 번째 요소가 dict라고 가정)
            word_sentences = word_sentences[0] if isinstance(word_sentences[0], dict) else {}
        
        if not isinstance(word_sentences, dict):
            raise ValueError("Word sentences data is not in the correct format.")   
    
    except ValueError as e:
        return render_template('error.html', message=str(e)), 400
    
    # JSON 필드인 'deleted_sentences'와 'word_sentences'를 처리하는 로직 수정
    deleted_sentences = review_session.deleted_sentences or {}
    if isinstance(deleted_sentences, str):
        try:
            deleted_sentences = json.loads(deleted_sentences)
        except json.JSONDecodeError as e:
            logging.error(f"JSON decoding error: {e}")
            return render_template('error.html', message="Error decoding deleted sentences."), 400

    # deleted_sentences를 second_review 필드로 필터링
    first_review_deleted_sentences = deleted_sentences.get('first_review', {})
    app.logger.debug(f"Second review deleted sentences: {first_review_deleted_sentences}")

    final_word_counts = review_session.final_word_counts or {}
    count_by_level = {}
    for level, words in levels.items():
        count = 0
        for word_info in words:
            word = word_info['word']
            count += final_word_counts.get(word, 0)
        count_by_level[level] = count
    # 실제 사용된 단어들만 필터링
    used_words = {word for word in word_sentences if word_sentences[word]}  # 단어 문장에 무언가 있을 때만 추가
    filtered_levels = {level: [word for word in words if word['word'] in used_words] for level, words in levels.items()}

    ebook_title = review_session.ebook_title[:-4] if review_session.ebook_title.endswith('.pdf') else review_session.ebook_title

     # 검토 단계를 한국어로 변환하여 변수에 저장
    review_stage_korean = {
        'not_reviewed': '<1차 검토>',
        'second_review_started': '<2차 검토>',
        'first_review_complete': '<2차 검토>',
        'second_review_complete': '<3차 검토>',
        'third_review_started': '<3차 검토>',
        'review_complete': '<3차 검토>'
    }.get(review_session.review_stage, '<미정의 단계>')   

    return render_template('show_results.html', levels=filtered_levels, deleted_sentences=deleted_sentences, review_stage=review_session.review_stage, review_stage_korean=review_stage_korean, review_session=review_session, count_by_level=count_by_level, word_sentences=word_sentences, unique_id=unique_id, ebook_title=ebook_title)


@app.route('/some_route')
def some_function():
    unique_id = request.args.get('unique_id', '')
    review_session = ReviewSession.query.filter_by(id=unique_id).first()
    if not review_session:
        return render_template('error.html', message="Session data not loaded properly."), 400

    # 서버에서 삭제된 문장 인덱스 목록을 불러옵니다.
    deleted_sentences = review_session.deleted_sentences or {}

    return render_template('show_results.html', review_session=review_session, deleted_sentences=deleted_sentences)


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
    unique_id = data['unique_id']
    increment = data['increment']
    formatted_uuid = UUID(unique_id, version=4)

    # UUID 검증과 포맷
    try:
        formatted_uuid = UUID(unique_id, version=4)
    except ValueError:
        return jsonify({"status": "error", "message": "Invalid UUID format"}), 400
    
    # 세션 데이터를 조회
    review_session = ReviewSession.query.filter_by(id=formatted_uuid).first()
    if not review_session:
        logging.error(f"Session not found for ID: {unique_id}")
        return jsonify({"status": "error", "message": "Session not found"}), 404

    # final_word_counts가 정의되지 않은 경우 초기화
    if review_session.final_word_counts is None:
        review_session.final_word_counts = {}

    # 단어가 final_word_counts에 없으면 초기화
    if word not in review_session.final_word_counts:
        review_session.final_word_counts[word] = 0

    # 단어의 카운트 업데이트 (0 이하로 내려가지 않도록 조치)
    new_count = max(0, review_session.final_word_counts[word] + increment)
    review_session.final_word_counts[word] = new_count    
    db.session.commit()

    # 업데이트된 카운트 로깅
    logging.info(f"Word '{word}' updated to {review_session.final_word_counts[word]} in session '{unique_id}'")
    return jsonify({'status': 'success', 'word': word, 'count': new_count})




@app.route('/complete_review/<unique_id>', methods=['POST'])
def complete_review(unique_id):
    logging.debug(f"Attempting to complete review for ID: {unique_id}")  # 로그 추가
    if not is_valid_uuid(unique_id):
        logging.error(f"Invalid UUID format: {unique_id}")  # 로그 추가
        return jsonify({'status': 'error', 'message': 'Invalid UUID format'}), 400

    review_session = ReviewSession.query.filter_by(id=unique_id).first()    
    if not review_session:
        logging.error(f"Review session not found for ID: {unique_id}")  # 로그 추가
        return jsonify({'status': 'error', 'message': 'Review session not found'}), 404

    next_stage = {
        'not_reviewed': 'first_review_complete',
        'first_review_complete': 'second_review_started',
        'second_review_started': 'second_review_complete',  # 이 부분이 빠져 있었을 수 있습니다.
        'second_review_complete': 'third_review_started',  # 추가된 부분
        'third_review_started': 'review_complete'  # 추가된 부분
    }
 
    current_stage = review_session.review_stage
    logging.debug(f"Current review stage: {current_stage}")  # 로그 추가
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



@app.route('/start_second_review/<unique_id>', methods=['POST'])
def start_second_review(unique_id):
    # UUID 검증
    if not is_valid_uuid(unique_id):
        logging.error("Invalid UUID format")
        return "Error: Invalid unique ID.", 400

    reviewer_name = request.form.get('reviewer_name')
    if not reviewer_name:
        return render_template('error.html', message="Reviewer name is required."), 400

    # 사용자 찾기 또는 새로 만들기
    user = User.query.filter_by(name=reviewer_name).first()
    if not user:
        user = User(name=reviewer_name)
        db.session.add(user)
        db.session.commit()

    # 데이터베이스에서 리뷰 세션 조회
    review_session = ReviewSession.query.filter_by(id=unique_id).first()
    if review_session:
        app.logger.debug(f"Review session loaded: {review_session}")
        app.logger.debug(f"Deleted sentences: {review_session.deleted_sentences}")
    if not review_session:
        logging.error("No valid session found for the given ID")
        return render_template('error.html', message="No valid session found for the given ID."), 404
    
        # 초기 로드 상태 로깅
    logging.debug(f"Initial deleted_sentences loaded: {review_session.deleted_sentences}")


    # JSON 데이터 처리
    if isinstance(review_session.word_sentences, str):
        try:
            word_sentences = json.loads(review_session.word_sentences)
        except json.JSONDecodeError as e:
            logging.error(f"JSON decoding error: {e}")
            return render_template('error.html', message="Error decoding word sentences."), 400
    elif isinstance(review_session.word_sentences, dict):
        word_sentences = review_session.word_sentences
    else:
        logging.error("Word sentences data is not in a supported format")
        return render_template('error.html', message="Error processing word sentences data."), 400
    
    if isinstance(review_session.deleted_sentences, str):
        try:
            deleted_sentences = json.loads(review_session.deleted_sentences)
        except json.JSONDecodeError as e:
            logging.error(f"JSON decoding error: {e}")
            return render_template('error.html', message="Error decoding word sentences."), 400
    elif isinstance(review_session.deleted_sentences, dict):
        deleted_sentences = review_session.deleted_sentences
    else:
        logging.error("deleted_sentences data is not in a supported format")
        return render_template('error.html', message="Error processing word sentences data."), 400

    # 리뷰 단계 및 사용자 ID 업데이트
    review_session.review_stage = 'second_review_started'
    review_session.user_id = user.id

    # deleted_sentences를 second_review 필드로 필터링
    second_review_deleted_sentences = deleted_sentences.get('second_review', {})
    app.logger.debug(f"Second review deleted sentences: {second_review_deleted_sentences}")

    db.session.commit()  # 데이터베이스에 변경 사항 저장
    return redirect(url_for('second_show_results',unique_id=unique_id))

@app.route('/start_third_review/<unique_id>', methods=['POST'])
def start_third_review(unique_id):
    # UUID 검증
    if not is_valid_uuid(unique_id):
        logging.error("Invalid UUID format")
        return "Error: Invalid unique ID.", 400

    reviewer_name = request.form.get('reviewer_name')
    if not reviewer_name:
        return render_template('error.html', message="Reviewer name is required."), 400

    # 사용자 찾기 또는 새로 만들기
    user = User.query.filter_by(name=reviewer_name).first()
    if not user:
        user = User(name=reviewer_name)
        db.session.add(user)
        db.session.commit()

    # 데이터베이스에서 리뷰 세션 조회
    review_session = ReviewSession.query.filter_by(id=unique_id).first()
    if review_session:
        app.logger.debug(f"Review session loaded: {review_session}")
        app.logger.debug(f"Deleted sentences: {review_session.deleted_sentences}")
    if not review_session:
        logging.error("No valid session found for the given ID")
        return render_template('error.html', message="No valid session found for the given ID."), 404
    
        # 초기 로드 상태 로깅
    logging.debug(f"Initial deleted_sentences loaded: {review_session.deleted_sentences}")

    # JSON 데이터 처리
    if isinstance(review_session.word_sentences, str):
        try:
            word_sentences = json.loads(review_session.word_sentences)
        except json.JSONDecodeError as e:
            logging.error(f"JSON decoding error: {e}")
            return render_template('error.html', message="Error decoding word sentences."), 400
    elif isinstance(review_session.word_sentences, dict):
        word_sentences = review_session.word_sentences
    else:
        logging.error("Word sentences data is not in a supported format")
        return render_template('error.html', message="Error processing word sentences data."), 400
    
    if isinstance(review_session.deleted_sentences, str):
        try:
            deleted_sentences = json.loads(review_session.deleted_sentences)
        except json.JSONDecodeError as e:
            logging.error(f"JSON decoding error: {e}")
            return render_template('error.html', message="Error decoding word sentences."), 400
    elif isinstance(review_session.deleted_sentences, dict):
        deleted_sentences = review_session.deleted_sentences
    else:
        logging.error("deleted_sentences data is not in a supported format")
        return render_template('error.html', message="Error processing word sentences data."), 400

    # 리뷰 단계 및 사용자 ID 업데이트
    review_session.review_stage = 'third_review_started'
    review_session.user_id = user.id


    # 변경사항을 데이터베이스에 다시 저장
    review_session.word_sentences = word_sentences
    review_session.deleted_sentences = deleted_sentences
    db.session.commit()

    return redirect(url_for('compare_results',unique_id=unique_id))

@app.route('/compare_results', methods=['GET'])
def compare_results():
    unique_id = request.args.get('unique_id')
    
    # UUID 검증
    if not is_valid_uuid(unique_id):
        return render_template('error.html', message="Invalid UUID format."), 400

    # UUID 형식 변경 (필요한 경우)
    if len(unique_id) == 32:  # UUID가 하이픈 없이 제공될 경우
        formatted_uuid = f"{unique_id[:8]}-{unique_id[8:12]}-{unique_id[12:16]}-{unique_id[16:20]}-{unique_id[20:]}"
        unique_id = formatted_uuid

    review_session = ReviewSession.query.filter_by(id=unique_id).first()
    if review_session:
        # JSON 필드인 'deleted_sentences'를 처리하는 로직 수정
        if isinstance(review_session.deleted_sentences, str):
            try:
                deleted_sentences = json.loads(review_session.deleted_sentences)
            except json.JSONDecodeError as e:
                logging.error(f"JSON decoding error: {e}")
                return render_template('error.html', message="Error decoding deleted sentences."), 400
        elif isinstance(review_session.deleted_sentences, dict):
            deleted_sentences = review_session.deleted_sentences
        else:
            deleted_sentences = {}  # 기본값 설정
        logging.debug(f"Loaded deleted_sentences: {review_session.deleted_sentences}")
        # 추가적으로 'levels' 필드가 필요하다면 여기서 처리
        levels = review_session.levels if review_session.levels else {}
        

    if not review_session:
        logging.error(f"No valid session found for ID: {unique_id}")
        return render_template('error.html', message="No valid session found for the given ID."), 404
    final_word_counts = review_session.final_word_counts or {}
    levels = review_session.levels
    try:
        word_sentences = review_session.word_sentences

        # 데이터 로드 후 타입 확인 및 변환
        if isinstance(word_sentences, list) and len(word_sentences) > 0:
            # 리스트 형태인 경우 첫 번째 요소 사용 (이 예제에서는 첫 번째 요소가 dict라고 가정)
            word_sentences = word_sentences[0] if isinstance(word_sentences[0], dict) else {}
        
        if not isinstance(word_sentences, dict):
            raise ValueError("Word sentences data is not in the correct format.")

    except ValueError as e:
        return render_template('error.html', message=str(e)), 400
    count_by_level = {}
    for level, words in levels.items():
        count = 0
        for word_info in words:
            word = word_info['word']
            count += final_word_counts.get(word, 0)
        count_by_level[level] = count
    # 실제 사용된 단어들만 필터링
    used_words = {word for word in word_sentences if word_sentences[word]}  # 단어 문장에 무언가 있을 때만 추가
    filtered_levels = {level: [word for word in words if word['word'] in used_words] for level, words in levels.items()}

    ebook_title = review_session.ebook_title[:-4] if review_session.ebook_title.endswith('.pdf') else review_session.ebook_title

     # 검토 단계를 한국어로 변환하여 변수에 저장
    review_stage_korean = {
        'not_reviewed': '<1차 검토>',
        'second_review_started': '<2차 검토>',
        'first_review_complete': '<2차 검토>',
        'second_review_complete': '<3차 검토>',
        'third_review_started': '<3차 검토>',
        'review_complete': '<3차 검토>'
    }.get(review_session.review_stage, '<미정의 단계>')   

    return render_template('compare_results.html', levels=filtered_levels, deleted_sentences=deleted_sentences, review_stage=review_session.review_stage, review_stage_korean=review_stage_korean, review_session=review_session, count_by_level=count_by_level, word_sentences=word_sentences, unique_id=unique_id, ebook_title=ebook_title)

@app.route('/second_show_results', methods=['GET'])
def second_show_results():
    unique_id = request.args.get('unique_id')
    
    # UUID 검증
    if not is_valid_uuid(unique_id):
        return render_template('error.html', message="Invalid UUID format."), 400

    # UUID 형식 변경 (필요한 경우)
    if len(unique_id) == 32:  # UUID가 하이픈 없이 제공될 경우
        formatted_uuid = f"{unique_id[:8]}-{unique_id[8:12]}-{unique_id[12:16]}-{unique_id[16:20]}-{unique_id[20:]}"
        unique_id = formatted_uuid

    review_session = ReviewSession.query.filter_by(id=unique_id).first()
    if review_session:
        # JSON 필드인 'deleted_sentences'를 처리하는 로직 수정
        if isinstance(review_session.deleted_sentences, str):
            try:
                deleted_sentences = json.loads(review_session.deleted_sentences)
            except json.JSONDecodeError as e:
                logging.error(f"JSON decoding error: {e}")
                return render_template('error.html', message="Error decoding deleted sentences."), 400
        elif isinstance(review_session.deleted_sentences, dict):
            deleted_sentences = review_session.deleted_sentences
        else:
            deleted_sentences = {}  # 기본값 설정
        logging.debug(f"Loaded deleted_sentences: {review_session.deleted_sentences}")
        # 추가적으로 'levels' 필드가 필요하다면 여기서 처리
        levels = review_session.levels if review_session.levels else {}
        

    if not review_session:
        logging.error(f"No valid session found for ID: {unique_id}")
        return render_template('error.html', message="No valid session found for the given ID."), 404
    levels = review_session.levels
    try:
        word_sentences = review_session.word_sentences

        # 데이터 로드 후 타입 확인 및 변환
        if isinstance(word_sentences, list) and len(word_sentences) > 0:
            # 리스트 형태인 경우 첫 번째 요소 사용 (이 예제에서는 첫 번째 요소가 dict라고 가정)
            word_sentences = word_sentences[0] if isinstance(word_sentences[0], dict) else {}
        
        if not isinstance(word_sentences, dict):
            raise ValueError("Word sentences data is not in the correct format.")   
    
    except ValueError as e:
        return render_template('error.html', message=str(e)), 400
    
    # JSON 필드인 'deleted_sentences'와 'word_sentences'를 처리하는 로직 수정
    deleted_sentences = review_session.deleted_sentences or {}
    if isinstance(deleted_sentences, str):
        try:
            deleted_sentences = json.loads(deleted_sentences)
        except json.JSONDecodeError as e:
            logging.error(f"JSON decoding error: {e}")
            return render_template('error.html', message="Error decoding deleted sentences."), 400


    # 2차 검토에서 제외된 문장만 반영
    second_review_deleted_sentences = deleted_sentences.get('second_review', {})

    final_word_counts = {}
    for word, sentences in word_sentences.items():
        if word in second_review_deleted_sentences:
            final_word_counts[word] = len(sentences) - len(second_review_deleted_sentences[word])
        else:
            final_word_counts[word] = len(sentences)


    count_by_level = {}
    for level, words in levels.items():
        count = 0
        for word_info in words:
            word = word_info['word']
            count += final_word_counts.get(word, 0)
        count_by_level[level] = count
    # 실제 사용된 단어들만 필터링
    used_words = {word for word in word_sentences if word_sentences[word]}  # 단어 문장에 무언가 있을 때만 추가
    filtered_levels = {level: [word for word in words if word['word'] in used_words] for level, words in levels.items()}

    ebook_title = review_session.ebook_title[:-4] if review_session.ebook_title.endswith('.pdf') else review_session.ebook_title

     # 검토 단계를 한국어로 변환하여 변수에 저장
    review_stage_korean = {
        'not_reviewed': '<1차 검토>',
        'second_review_started': '<2차 검토>',
        'first_review_complete': '<2차 검토>',
        'second_review_complete': '<3차 검토>',
        'third_review_started': '<3차 검토>',
        'review_complete': '<3차 검토>'
    }.get(review_session.review_stage, '<미정의 단계>')   

    return render_template('second_show_results.html', levels=filtered_levels, deleted_sentences=deleted_sentences, review_stage=review_session.review_stage, review_stage_korean=review_stage_korean, review_session=review_session, count_by_level=count_by_level, word_sentences=word_sentences, unique_id=unique_id, ebook_title=ebook_title)

@app.route('/some_route')
def some_route():
    session.permanent = True  # 세션 만료를 PERMANENT_SESSION_LIFETIME 설정에 따라 결정
    # 세션 데이터 작업
    return 'Something'



@app.route('/final_results')
def final_results():
    unique_id = request.args.get('unique_id')
    review_session = ReviewSession.query.filter_by(id=unique_id).first()
    final_counts = session.get('final_counts', {})  # 세션에서 최종 계산된 데이터를 가져옵니다.

    if not review_session:
        logging.error(f"No valid session found for ID: {unique_id}")
        return render_template('error.html', message="No valid session found."), 404

    levels = review_session.levels or {}
    word_sentences = review_session.word_sentences
    final_word_counts = review_session.final_word_counts or {}

    if not levels or not word_sentences:
        return render_template('error.html', message="Data not loaded properly. Please try again."), 400

    analysis_time = datetime.now()  # 현재 시간을 생성
    review_stage_korean = {
        'not_reviewed': '미검토',
        'first_review_complete': '1차 검토',
        'second_review_complete': '2차 검토',
        'third_review_started': '3차 검토',
        'review_complete': '3차 검토'
    }.get(review_session.review_stage, '미정의 단계')

    user = User.query.get(review_session.user_id)
    if not user:
        return render_template('error.html', message="User not found."), 404

    ebook_title = review_session.ebook_title[:-4] if review_session.ebook_title.endswith('.pdf') else review_session.ebook_title

    # Redefine the calculations for clarity
    count_by_level = {}
    sum_counts_by_level = {}
    for level, words in levels.items():
        count = 0
        total_occurrences = 0
        for word_info in words:
            word = word_info['word']
            if word in final_word_counts:
                count += 1  # Increment for each distinct word found
                total_occurrences += final_word_counts.get(word, 0)  # Add the occurrences of the word
        count_by_level[level] = count
        sum_counts_by_level[level] = total_occurrences

    logging.debug(f"Loaded final_word_counts: {final_word_counts}")
    logging.debug(f"Loaded levels: {levels}")
    logging.debug(f"Calculated count_by_level: {count_by_level}")
    logging.debug(f"Calculated sum_counts_by_level: {sum_counts_by_level}")

    # Save the calculated counts in the session
    session['final_counts'] = sum_counts_by_level

    # Update the session with the calculated counts for count_by_level as well
    session['count_by_level'] = count_by_level

    # Prepare JSON data for the download_table_excel function
    table_data = json.dumps({
        'countData': count_by_level,
        'sumData': sum_counts_by_level
    })

    # 자동으로 엑셀 파일 생성 및 이메일 전송
    with app.test_request_context(method='POST'):
        request.form = MultiDict([
            ('tableData', table_data),
            ('ebookTitle', f"{review_stage_korean}_{ebook_title}")
        ])
        download_table_excel(unique_id)

    return render_template('final_results.html', review_stage=review_stage_korean, ebook_title=ebook_title,
                           reviewer_name=user.name, analysis_time=analysis_time,
                           sum_counts_by_level=final_counts,
                           count_by_level=count_by_level, unique_id=unique_id)

@app.route('/submit_final_counts', methods=['POST'])
def submit_final_counts():
    data = request.get_json()
    unique_id = data['unique_id']
    sum_counts_by_level = data['sumCountsByLevel']

    # 여기서는 예제로 데이터를 세션에 저장하겠습니다.
    session['final_counts'] = sum_counts_by_level

    return jsonify({"status": "success"})



@app.route('/update_review', methods=['POST'])
def update_review():
    data = request.get_json()
    session_id = data['unique_id']
    word = data['word']
    sentence_indexes = list(map(int, data['sentence_indexes']))  # 입력된 인덱스를 정수로 변환

    # 데이터베이스 세션 리프레쉬
    db.session.commit()  # 현재까지의 변경 사항을 커밋    
    db.session.expire_all()
    review_session = ReviewSession.query.get(session_id)
    if not review_session:
        logging.error(f"Session not found for ID: {session_id}")
        return jsonify({'error': 'Session not found'}), 404
    
    # 데이터 타입 확인 및 딕셔너리 변환
    try:
        # word_sentences가 문자열이면 JSON으로 파싱
        if isinstance(review_session.word_sentences, str):
            word_sentences = json.loads(review_session.word_sentences)
        elif isinstance(review_session.word_sentences, dict):
            word_sentences = review_session.word_sentences
        else:
            word_sentences = {}  # 기본값 설정
            print("word_sentences was not a dictionary or string, initialized to empty dict.")

    except json.JSONDecodeError as e:
        print(f"JSON decoding error: {e}")  # JSON 파싱 오류 로깅
        word_sentences = {}  # 파싱 실패 시 초기화
    
    if None in sentence_indexes:
        logging.error("Invalid sentence indexes provided")
        return jsonify({'error': 'Invalid sentence indexes provided'}), 400

    
    # 단어 데이터 가져오기 및 초기화
    word_data = word_sentences.get(word, {'sentences': []})
    if isinstance(word_data, list):  # 이 경우는 구조가 잘못된 경우임
        logging.info("Word data was a list, converting to dict with sentences")
        word_data = {'sentences': [{'text': s, 'deleted': False} for s in word_data]}

    # 기존 데이터 확인
    if isinstance(review_session.deleted_sentences, str):
        deleted_sentences = json.loads(review_session.deleted_sentences)
    else:
        deleted_sentences = review_session.deleted_sentences or {}
  
    # 문장 삭제 정보 업데이트
    for index in sentence_indexes:
        if word not in deleted_sentences:
            deleted_sentences[word] = []
        if index not in deleted_sentences[word]:
            deleted_sentences[word].append(index)
            logging.debug(f"Adding index {index} to deleted_sentences for word '{word}'")

    word_sentences[word] = word_data
    review_session.word_sentences = word_sentences  
    review_session.deleted_sentences = json.dumps(deleted_sentences)
    db.session.commit()
    logging.debug(f"Updated deleted_sentences: {review_session.deleted_sentences}")    

    # 응답 반환
    return jsonify({'success': 'Data updated'}), 200

from email.header import Header  # 이메일 헤더 인코딩을 위해 필요

def send_email_with_smtplib(recipient, subject, body, excel_data, filename):
    sender_email = "pbh1527@gmail.com"
    sender_password = "gljo xpuj rous xgaz"

    # 이메일 구성
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = recipient
    msg['Subject'] = Header(subject, 'utf-8')

    # 본문 추가
    msg.attach(MIMEText(body, 'plain', 'utf-8'))

    # 파일 첨부
    part = MIMEBase('application', 'octet-stream')
    part.set_payload(excel_data.getvalue())
    encoders.encode_base64(part)
    part.add_header('Content-Disposition', 'attachment', filename=Header(filename, 'utf-8').encode())
    msg.attach(part)

    # 서버 연결 및 이메일 전송
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        text = msg.as_bytes()
        server.sendmail(sender_email, recipient, text)
        server.quit()
        print("Email sent successfully")
    except Exception as e:
        print(f"Failed to send email: {e}")
    
@app.route('/download_table_excel/<unique_id>', methods=['POST'])
def download_table_excel(unique_id):
    # Ensure the upload directory exists
    upload_folder = os.path.join(current_app.root_path, app.config['UPLOAD_FOLDER'])
    os.makedirs(upload_folder, exist_ok=True)


    # Extract and parse the table data from the form
    table_data = request.form.get('tableData')
    ebook_title = request.form.get('ebookTitle')  # Get the ebook title

    if not table_data:
        return "No data provided", 400
    
    try:
        data = json.loads(table_data)
    except json.JSONDecodeError as e:
        logging.error(f"JSON decoding error: {e}")
        return "Invalid JSON data", 400

    count_data = data.get('countData')
    sum_data = data.get('sumData')

    # 로그 추가
    logging.debug(f"Received count_data: {count_data}")
    logging.debug(f"Received sum_data: {sum_data}")

                # Retrieve the review session data
    review_session = ReviewSession.query.filter_by(id=unique_id).first()
    if not review_session:
        return "Review session not found", 404

        # Parse the word sentences and filter out deleted sentences
    word_sentences = review_session.word_sentences or {}
    if isinstance(word_sentences, str):
        word_sentences = json.loads(word_sentences)

    deleted_sentences = review_session.deleted_sentences or {}
    if isinstance(deleted_sentences, str):
        deleted_sentences = json.loads(deleted_sentences)

    levels = review_session.levels or {}
    if isinstance(levels, str):
        levels = json.loads(levels)

        # Filter out the deleted sentences
    filtered_sentences = {}
    for word, sentences in word_sentences.items():
        filtered_sentences[word] = [s for i, s in enumerate(sentences) if i not in deleted_sentences.get(word, [])]

    # Ensure data is in list form
    count_data_list = [list(count_data.values())] if count_data else [[]]
    sum_data_list = [list(sum_data.values())] if sum_data else [[]]
    # Create DataFrames from the data
    try:
        df_counts = pd.DataFrame(count_data_list, columns=['Level 1', 'Level 2', 'Level 3', 'Level 4'])
        df_sums = pd.DataFrame(sum_data_list, columns=['Level 1', 'Level 2', 'Level 3', 'Level 4'])
    except ValueError as e:
        logging.error(f"Error creating DataFrames: {e}")
        return "Error creating Excel data", 500

        # Prepare DataFrame for word sentences with levels
    sentence_data = []
    for level, words in levels.items():
        for word_info in words:
            word = word_info['word']
            sentences = filtered_sentences.get(word, [])
            for sentence in sentences:
                sentence_data.append({"Level": level, "Word": word, "Sentence": sentence})
    df_sentences = pd.DataFrame(sentence_data)
        
    output = BytesIO()
        # Save to Excel
    filename = f"{ebook_title}.xlsx"  # Use the ebook title for the filename
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_counts.to_excel(writer, sheet_name='Counts by Level', index=False)
        df_sums.to_excel(writer, sheet_name='Sum Counts by Level', index=False)
        df_sentences.to_excel(writer, sheet_name='Word Sentences', index=False)
    output.seek(0)

    # 이메일 전송
    recipient_email = 'pbh1527@gmail.com'  # 실제 이메일 주소로 변경
    subject = f"{review_session.review_stage} - {ebook_title} 분석 결과"
    body = f"{ebook_title}의 분석 결과를 첨부합니다."
    send_email_with_smtplib(recipient_email, subject, body, output, f"{ebook_title}.xlsx")
                
    return send_file(output, as_attachment=True, download_name=filename)




@app.template_filter('enumerate')
def jinja2_filter_enumerate(sequence, start=1):
    return enumerate(sequence, start)


@app.route('/save_word_counts', methods=['POST'])
def save_word_counts():
    data = request.json
    session['word_counts'] = data
    return jsonify({"status": "success"})



if __name__ == '__main__':
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    app.run(debug=True)