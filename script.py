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

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SESSION_TYPE'] = 'filesystem'  # 세션 데이터를 파일 시스템에 저장
Session(app)  # Flask-Session 구성

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf', 'xlsx'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def find_word_sentences(pdf_path, words):
    """Find sentences containing any of the specified words in a PDF."""
    doc = fitz.open(pdf_path)
    word_sentences = defaultdict(list)
    for page in doc:
        text = page.get_text("text")
        sentences = text.split('. ')
        for sentence in sentences:
            for word_info in words:
                if word_info['word'].lower() in sentence.lower():
                    word_sentences[word_info['word']].append(sentence)
    return dict(word_sentences)

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
        unique_id = uuid.uuid4().hex  # Generating a unique ID for this session
        session['unique_id'] = unique_id  # Storing unique ID in session
        
        wordlist_file = request.files['wordlist']
        ebook_file = request.files['ebook']
        if not (wordlist_file and allowed_file(wordlist_file.filename)) or not (ebook_file and allowed_file(ebook_file.filename)):
            return render_template('upload.html', message='Invalid file or extension.')
        
        wordlist_path = os.path.join(app.config['UPLOAD_FOLDER'], wordlist_file.filename)
        ebook_path = os.path.join(app.config['UPLOAD_FOLDER'], ebook_file.filename)
        wordlist_file.save(wordlist_path)
        ebook_file.save(ebook_path)
        
        levels = read_excel_file(wordlist_path)
        session[f'levels_{unique_id}'] = levels  # Using unique_id in session key
        
        all_words = [word for level in levels.values() for word in level]
        word_sentences = find_word_sentences(ebook_path, all_words)
        session[f'word_sentences_{unique_id}'] = word_sentences  # Using unique_id in session key
        return redirect(url_for('show_results', unique_id=unique_id))
    return render_template('upload.html')



@app.route('/show_results', methods=['GET'])
def show_results():
    unique_id = request.args.get('unique_id')  # URL 매개변수에서 unique_id를 가져옵니다.
    levels = session.get(f'levels_{unique_id}', {})  # unique_id를 사용해 데이터를 조회합니다.
    word_sentences = session.get(f'word_sentences_{unique_id}', {})  # unique_id를 사용해 데이터를 조회합니다.

    if not levels or not word_sentences:
        return "Error: Levels or word sentences data not loaded properly.", 400

     # `final_word_counts`를 unique_id를 사용하여 세션에서 가져옵니다.
    final_word_counts = session.get(f'final_word_counts_{unique_id}', {})
    for word, sentences in word_sentences.items():
        if word not in final_word_counts:
            final_word_counts[word] = len(sentences)
# 수정된 `final_word_counts`를 다시 세션에 저장할 때 unique_id를 사용합니다.
        session[f'final_word_counts_{unique_id}'] = final_word_counts


    return render_template('show_results.html', levels=levels, word_sentences=word_sentences, unique_id=unique_id)


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






@app.route('/final_results')
def final_results():
    unique_id = request.args.get('unique_id')
    levels = session.get(f'levels_{unique_id}', {})
    final_word_counts = session.get(f'final_word_counts_{unique_id}', {})

    if not levels or not final_word_counts:
        return "Error: Data not loaded properly.", 400

    count_by_level = {}
    for level, words in levels.items():
        # 해당 수준의 각 단어에 대해 final_word_counts에서 카운트를 가져와 합산합니다.
        count_by_level[level] = sum(final_word_counts.get(word['word'], 0) for word in words)

    sum_counts_by_level = {}
    for level, words in levels.items():
        # 해당 수준의 단어가 final_word_counts에 한 번이라도 등장했다면 카운트합니다.
        sum_counts_by_level[level] = sum(1 for word in words if final_word_counts.get(word['word'], 0) > 0)

    return render_template('final_results.html', count_by_level=count_by_level, sum_counts_by_level=sum_counts_by_level)











@app.route('/save_word_counts', methods=['POST'])
def save_word_counts():
    data = request.json
    session['word_counts'] = data
    return jsonify({"status": "success"})



if __name__ == '__main__':
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    app.run(debug=True)