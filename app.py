from flask import Flask, request, jsonify
from yt_dlp import YoutubeDL

app = Flask(__name__)

@app.route('/', methods=['GET'])
def home():
    return jsonify({"status": "running", "message": "Backend is active!"})

@app.route('/search', methods=['GET'])
def search():
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({'error': 'کیوری درکار ہے'}), 400

    ydl_opts = {
        'quiet': True,
        'skip_download': True,
        'extract_flat': True,
    }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            search_query = f"ytsearch20:{query}"
            info = ydl.extract_info(search_query, download=False)
            
            results = []
            for entry in info.get('entries', []):
                results.append({
                    'id': entry.get('id'),
                    'title': entry.get('title'),
                    'duration': entry.get('duration'),
                    'uploader': entry.get('uploader'),
                    'url': f"https://www.youtube.com/watch?v={entry.get('id')}",
                    'thumbnail': f"https://i.ytimg.com/vi/{entry.get('id')}/hqdefault.jpg"
                })

            return jsonify({'success': True, 'results': results})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/get-download-links', methods=['POST'])
def get_download_links():
    data = request.get_json()
    video_url = data.get('url') if data else None

    if not video_url:
        return jsonify({'error': 'ویڈیو URL درکار ہے'}), 400

    ydl_opts = {
        'quiet': True,
        'skip_download': True,
        'format': 'best',
    }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            
            formats = []
            for f in info.get('formats', []):
                if f.get('url') and f.get('ext') in ['mp4', 'm4a', 'mp3', 'webm']:
                    formats.append({
                        'format_id': f.get('format_id'),
                        'quality': f.get('format_note') or f.get('resolution') or 'Audio',
                        'ext': f.get('ext'),
                        'direct_url': f.get('url')
                    })

            return jsonify({
                'success': True,
                'title': info.get('title'),
                'thumbnail': info.get('thumbnail'),
                'formats': formats
            })
    except Exception as e:
        return jsonify({'error': 'لنکس حاصل نہیں ہو سکے'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
