from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import yt_dlp
import os
import uuid
import re
import tempfile

app = Flask(__name__)
CORS(app)

DOWNLOAD_DIR = tempfile.mkdtemp()

def is_valid_url(url):
    pattern = re.compile(
        r'^https?://'
        r'(?:www\.)?'
        r'(?:instagram\.com|tiktok\.com|facebook\.com|fb\.watch|'
        r'twitter\.com|x\.com|pinterest\.com|pin\.it|'
        r'snapchat\.com|threads\.net|youtube\.com|youtu\.be|'
        r'vimeo\.com|dailymotion\.com|reddit\.com)'
        r'.*$', re.IGNORECASE
    )
    return bool(pattern.match(url))

@app.route('/')
def home():
    return jsonify({"status": "ok", "message": "قشمرة Save API تشتغل ✅"})

@app.route('/api/info', methods=['POST'])
def get_info():
    data = request.get_json()
    url = data.get('url', '').strip()

    if not url:
        return jsonify({"error": "الرابط فاضي"}), 400

    if not is_valid_url(url):
        return jsonify({"error": "الرابط غير مدعوم. تأكد من أنه من منصة مدعومة"}), 400

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        formats = []
        seen = set()
        for f in (info.get('formats') or []):
            height = f.get('height')
            ext = f.get('ext')
            if height and ext in ['mp4', 'webm']:
                label = f"{height}p {ext.upper()}"
                if label not in seen:
                    seen.add(label)
                    formats.append({
                        "format_id": f.get('format_id'),
                        "label": label,
                        "height": height,
                        "ext": ext,
                        "filesize": f.get('filesize'),
                    })

        formats.sort(key=lambda x: x['height'], reverse=True)

        # Add MP3 option
        formats.append({"format_id": "mp3", "label": "MP3 صوت فقط", "height": 0, "ext": "mp3", "filesize": None})

        duration = info.get('duration')
        if duration:
            mins = int(duration // 60)
            secs = int(duration % 60)
            duration_str = f"{mins}:{secs:02d}"
        else:
            duration_str = "غير معروف"

        return jsonify({
            "title": info.get('title', 'بدون عنوان'),
            "uploader": info.get('uploader') or info.get('channel') or 'غير معروف',
            "thumbnail": info.get('thumbnail', ''),
            "duration": duration_str,
            "platform": info.get('extractor_key', 'Unknown'),
            "formats": formats[:8],
        })

    except yt_dlp.utils.DownloadError as e:
        msg = str(e)
        if 'Private' in msg or 'private' in msg:
            return jsonify({"error": "المنشور خاص ولا يمكن تحميله"}), 400
        if 'not available' in msg:
            return jsonify({"error": "المنشور غير متاح أو محذوف"}), 400
        return jsonify({"error": "تعذر معالجة الرابط. تأكد أن المنشور عام"}), 400
    except Exception as e:
        return jsonify({"error": "حدث خطأ غير متوقع، حاول مجدداً"}), 500


@app.route('/api/download', methods=['POST'])
def download_video():
    data = request.get_json()
    url = data.get('url', '').strip()
    format_id = data.get('format_id', 'best')

    if not url or not is_valid_url(url):
        return jsonify({"error": "رابط غير صحيح"}), 400

    file_id = str(uuid.uuid4())
    out_path = os.path.join(DOWNLOAD_DIR, file_id)

    if format_id == 'mp3':
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': out_path + '.%(ext)s',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': True,
        }
        final_ext = 'mp3'
    else:
        ydl_opts = {
            'format': format_id if format_id != 'best' else 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': out_path + '.%(ext)s',
            'merge_output_format': 'mp4',
            'quiet': True,
        }
        final_ext = 'mp4'

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        final_file = out_path + '.' + final_ext
        if not os.path.exists(final_file):
            for f in os.listdir(DOWNLOAD_DIR):
                if f.startswith(file_id):
                    final_file = os.path.join(DOWNLOAD_DIR, f)
                    final_ext = f.split('.')[-1]
                    break

        mime = 'audio/mpeg' if final_ext == 'mp3' else 'video/mp4'
        filename = f"qashmra_save_{file_id[:8]}.{final_ext}"

        return send_file(
            final_file,
            mimetype=mime,
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        return jsonify({"error": "فشل التحميل، حاول مجدداً"}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
